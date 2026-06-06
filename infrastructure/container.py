"""DI 容器：組裝 settings / repo / agent / stores / use cases。Infrastructure 層。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from application.use_cases.clarification import AnswerClarification
from application.use_cases.compliance import CheckCompliance
from application.use_cases.feedback import SubmitFeedback
from application.use_cases.followup import FollowUpTask
from application.use_cases.provide_credentials import ProvideCredentials
from application.use_cases.run_browser_job import RunBrowserJob
from application.use_cases.steering import PauseJob, ResumeJob, SteerJob, StopJob
from application.use_cases.submit_task import SubmitTask
from domain.ports import (
    BrowserAgentPort,
    DomainThrottle,
    FeedbackPort,
    LearningStore,
    SessionStore,
    SteeringRegistry,
    TaskRepo,
)
from infrastructure.credentials import InMemoryCredentialVault
from infrastructure.events import InMemoryEventBroker
from infrastructure.feedback import InMemoryFeedbackStore
from infrastructure.learning import InMemoryLearningStore
from infrastructure.session.stores import InMemorySessionStore
from infrastructure.steering_registry import InMemorySteeringRegistry


@dataclass
class Container:
    repo: TaskRepo
    agent: BrowserAgentPort
    max_steps: int = 40
    broker: InMemoryEventBroker = field(default_factory=InMemoryEventBroker)
    registry: SteeringRegistry = field(default_factory=InMemorySteeringRegistry)
    feedback_store: FeedbackPort = field(default_factory=InMemoryFeedbackStore)
    session_store: SessionStore = field(default_factory=InMemorySessionStore)
    learning: LearningStore = field(default_factory=InMemoryLearningStore)
    compliance: CheckCompliance | None = None
    throttle: DomainThrottle | None = None
    default_handoff_policy: str = "ai_then_human"
    credentials: InMemoryCredentialVault = field(default_factory=InMemoryCredentialVault)

    @classmethod
    def create(
        cls,
        *,
        db_url: str = "sqlite:///wagent.db",
        agent: BrowserAgentPort | None = None,
        settings: Any = None,
    ) -> Container:
        from adapters.agents.browser_use_gateway import BrowserUseGateway
        from adapters.persistence.sql_feedback_store import SqlFeedbackStore
        from adapters.persistence.sql_learning_store import SqlLearningStore
        from adapters.persistence.sql_task_repo import SqlTaskRepo
        from infrastructure.browseruse.agent_factory import make_browser_use_agent_factory
        from infrastructure.compliance import UrllibRobotsChecker
        from infrastructure.config import get_settings
        from infrastructure.db import make_engine, session_factory
        from infrastructure.session.stores import FileSessionStore
        from infrastructure.throttle import InMemoryDomainThrottle

        s = settings or get_settings()
        engine = make_engine(db_url)
        sf = session_factory(engine)
        default_agent = BrowserUseGateway(agent_factory=make_browser_use_agent_factory(s))
        return cls(
            repo=SqlTaskRepo(sf),
            agent=agent or default_agent,
            max_steps=s.max_steps,
            feedback_store=SqlFeedbackStore(sf),
            session_store=FileSessionStore(),
            learning=SqlLearningStore(sf),
            compliance=CheckCompliance(
                robots=UrllibRobotsChecker(),
                denylist=s.denylist_items(),
                respect_robots=s.respect_robots,
                user_agent=s.user_agent,
            ),
            throttle=InMemoryDomainThrottle(s.min_domain_interval_sec),
            default_handoff_policy=s.handoff_policy,
        )

    @classmethod
    def for_testing(
        cls, *, repo: TaskRepo, agent: BrowserAgentPort, max_steps: int = 40
    ) -> Container:
        return cls(repo=repo, agent=agent, max_steps=max_steps)

    # --- use case 工廠 ---
    def submit_task(self) -> SubmitTask:
        return SubmitTask(self.repo)

    def run_browser_job(self) -> RunBrowserJob:
        return RunBrowserJob(
            self.repo,
            self.agent,
            max_steps=self.max_steps,
            publisher=self.broker,
            registry=self.registry,
            compliance=self.compliance,
            throttle=self.throttle,
            learning=self.learning,
            default_policy=self.default_handoff_policy,
            credentials=self.credentials,
        )

    def provide_credentials(self) -> ProvideCredentials:
        return ProvideCredentials(self.credentials)

    def steer_job(self) -> SteerJob:
        return SteerJob(self.repo, self.registry, self.broker)

    def pause_job(self) -> PauseJob:
        return PauseJob(self.repo, self.registry, self.broker)

    def resume_job(self) -> ResumeJob:
        return ResumeJob(self.repo, self.registry, self.broker)

    def stop_job(self) -> StopJob:
        return StopJob(self.repo, self.registry, self.broker)

    def answer_clarification(self) -> AnswerClarification:
        return AnswerClarification(self.repo, self.registry, self.broker)

    def submit_feedback(self) -> SubmitFeedback:
        return SubmitFeedback(self.repo, self.feedback_store, learning=self.learning)

    def follow_up_task(self) -> FollowUpTask:
        return FollowUpTask(self.repo)
