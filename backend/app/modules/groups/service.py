"""Group planning use cases. Only members can see a group; only the owner decides."""

from __future__ import annotations

import secrets
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import Conflict, Forbidden, NotFound
from app.modules.auth.models import User
from app.modules.groups.consensus import VOTE_NAMES, VOTE_VALUES, OptionTally, explain, rank
from app.modules.groups.models import GroupMember, GroupVote, TripGroup
from app.modules.notifications.service import NotificationService
from app.modules.planner.models import TripPlan
from app.modules.planner.schemas import BundleOut, PlanRequest
from app.modules.search.pricing import MoneyOut

MAX_MEMBERS = 12
Vote = Literal["love", "ok", "no", "none"]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    name: str
    role: str
    max_budget_per_person: int | None
    votes_cast: int
    is_me: bool


class GroupOptionOut(BaseModel):
    option: BundleOut
    per_person: MoneyOut
    love: int
    ok: int
    no: int
    score: int
    over_budget_for: list[str]
    my_vote: Vote
    position: int


class GroupOut(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    title: str
    request: PlanRequest
    status: Literal["open", "decided"]
    invite_code: str | None = Field(description="Shown to members so anyone can invite")
    is_owner: bool
    members: list[MemberOut]
    options: list[GroupOptionOut]
    leader_option_id: str | None
    consensus: str
    decided_option_id: str | None


class GroupSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    members: int
    is_owner: bool


class GroupService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._notify = NotificationService(session)

    # ------------------------------------------------------------------ access

    def _membership(self, user: User, group_id: uuid.UUID) -> tuple[TripGroup, GroupMember]:
        group = self._session.get(TripGroup, group_id)
        member = (
            self._session.scalar(
                select(GroupMember).where(
                    GroupMember.group_id == group_id, GroupMember.user_id == user.id
                )
            )
            if group
            else None
        )
        if group is None or member is None:
            raise NotFound("Group not found.", code="GROUP_NOT_FOUND")
        return group, member

    def _plan(self, group: TripGroup) -> TripPlan:
        plan = self._session.get(TripPlan, group.plan_id)
        if plan is None:
            raise NotFound("Group not found.", code="GROUP_NOT_FOUND")
        return plan

    # ------------------------------------------------------------------ use cases

    def create(self, user: User, plan_id: uuid.UUID) -> GroupOut:
        plan = self._session.get(TripPlan, plan_id)
        if plan is None or plan.user_id != user.id:
            raise NotFound("Plan not found.", code="PLAN_NOT_FOUND")
        if not plan.options:
            raise Conflict("This plan has no options to vote on.", code="PLAN_EMPTY")
        existing = self._session.scalar(select(TripGroup).where(TripGroup.plan_id == plan_id))
        if existing is not None:
            return self.get(user, existing.id)
        group = TripGroup(
            plan_id=plan_id, owner_id=user.id, status="open", invite_code=secrets.token_urlsafe(9)
        )
        self._session.add(group)
        self._session.flush()
        self._session.add(
            GroupMember(
                group_id=group.id, user_id=user.id, role="owner", joined_at=self._clock.now()
            )
        )
        try:
            self._session.commit()
        except IntegrityError:  # the same plan shared twice at once
            self._session.rollback()
            existing = self._session.scalar(select(TripGroup).where(TripGroup.plan_id == plan_id))
            if existing is None:
                raise
            return self.get(user, existing.id)
        return self.get(user, group.id)

    def join(self, user: User, invite_code: str) -> GroupOut:
        group = self._session.scalar(select(TripGroup).where(TripGroup.invite_code == invite_code))
        if group is None:
            raise NotFound("This invite link is not valid.", code="INVITE_INVALID")
        member = self._session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group.id, GroupMember.user_id == user.id
            )
        )
        if member is not None:
            return self.get(user, group.id)
        if group.status != "open":
            raise Conflict("This group has already decided.", code="GROUP_DECIDED")
        count = (
            self._session.scalar(
                select(func.count())
                .select_from(GroupMember)
                .where(GroupMember.group_id == group.id)
            )
            or 0
        )
        if count >= MAX_MEMBERS:
            raise Conflict(f"Groups are limited to {MAX_MEMBERS} people.", code="GROUP_FULL")
        now = self._clock.now()
        self._session.add(
            GroupMember(group_id=group.id, user_id=user.id, role="member", joined_at=now)
        )
        self._notify.notify(
            user_id=group.owner_id,
            kind="group",
            title="Someone joined your group",
            body=f"{user.full_name} joined and can now vote.",
            link=f"/groups/{group.id}",
            now=now,
            email=False,
        )
        try:
            self._session.commit()
        except IntegrityError:  # joined twice at once
            self._session.rollback()
        return self.get(user, group.id)

    def vote(self, user: User, group_id: uuid.UUID, option_id: str, vote: Vote) -> GroupOut:
        group, _ = self._membership(user, group_id)
        if group.status != "open":
            raise Conflict("Voting has closed.", code="GROUP_DECIDED")
        if not any(o["id"] == option_id for o in self._plan(group).options):
            raise NotFound("Option not found.", code="OPTION_NOT_FOUND")
        self._session.execute(
            delete(GroupVote).where(
                GroupVote.group_id == group_id,
                GroupVote.user_id == user.id,
                GroupVote.option_id == option_id,
            )
        )
        if vote != "none":
            self._session.add(
                GroupVote(
                    group_id=group_id,
                    user_id=user.id,
                    option_id=option_id,
                    value=VOTE_VALUES[vote],
                    updated_at=self._clock.now(),
                )
            )
        self._session.commit()
        return self.get(user, group_id)

    def set_budget(self, user: User, group_id: uuid.UUID, budget: int | None) -> GroupOut:
        _, member = self._membership(user, group_id)
        member.max_budget_per_person = budget
        self._session.commit()
        return self.get(user, group_id)

    def decide(self, user: User, group_id: uuid.UUID, option_id: str) -> GroupOut:
        group, member = self._membership(user, group_id)
        if member.role != "owner":
            raise Forbidden("Only the person who shared the plan can decide.")
        if not any(o["id"] == option_id for o in self._plan(group).options):
            raise NotFound("Option not found.", code="OPTION_NOT_FOUND")
        now = self._clock.now()
        group.status, group.decided_option_id, group.decided_at = "decided", option_id, now
        members = self._session.scalars(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id != user.id
            )
        )
        for other in members:
            self._notify.notify(
                user_id=other.user_id,
                kind="group",
                severity="success",
                title="Your group picked a trip",
                body=f"{user.full_name} chose the option for the group.",
                link=f"/groups/{group_id}",
                now=now,
                email=False,
            )
        self._session.commit()
        return self.get(user, group_id)

    def leave(self, user: User, group_id: uuid.UUID) -> None:
        group, member = self._membership(user, group_id)
        if member.role == "owner":
            raise Conflict("The owner cannot leave their own group.", code="OWNER_CANNOT_LEAVE")
        self._session.execute(
            delete(GroupVote).where(GroupVote.group_id == group.id, GroupVote.user_id == user.id)
        )
        self._session.delete(member)
        self._session.commit()

    def mine(self, user: User) -> list[GroupSummaryOut]:
        rows = self._session.execute(
            select(TripGroup, TripPlan.title)
            .join(GroupMember, GroupMember.group_id == TripGroup.id)
            .join(TripPlan, TripPlan.id == TripGroup.plan_id)
            .where(GroupMember.user_id == user.id)
            .order_by(TripGroup.created_at.desc())
        ).all()
        counts = dict(
            self._session.execute(
                select(GroupMember.group_id, func.count()).group_by(GroupMember.group_id)
            ).all()
        )
        return [
            GroupSummaryOut(
                id=g.id,
                title=title,
                status=g.status,
                members=counts.get(g.id, 0),
                is_owner=g.owner_id == user.id,
            )
            for g, title in rows
        ]

    # ------------------------------------------------------------------ view

    def get(self, user: User, group_id: uuid.UUID) -> GroupOut:
        group, me = self._membership(user, group_id)
        plan = self._plan(group)
        request = PlanRequest.model_validate(plan.request)
        options = [BundleOut.model_validate(o) for o in plan.options]
        members = self._session.execute(
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.joined_at)
        ).all()
        votes = list(self._session.scalars(select(GroupVote).where(GroupVote.group_id == group_id)))
        first_names = {u.id: u.full_name.split()[0] for _, u in members}

        tallies = {
            o.id: OptionTally(
                option_id=o.id,
                plan_rank=o.rank,
                per_person_minor=o.total.amount_minor // request.adults,
            )
            for o in options
        }
        for v in votes:
            tally = tallies.get(v.option_id)
            if tally is not None:
                name = VOTE_NAMES[v.value]
                setattr(tally, name, getattr(tally, name) + 1)
        for m, _ in members:
            if m.max_budget_per_person is None:
                continue
            for tally in tallies.values():
                if tally.per_person_minor > m.max_budget_per_person * 100:
                    tally.over_budget.append(first_names[m.user_id])
        ordered = rank(list(tallies.values()))
        leader = ordered[0] if ordered else None
        mine = {v.option_id: VOTE_NAMES[v.value] for v in votes if v.user_id == user.id}
        by_id = {o.id: o for o in options}
        currency = options[0].total.currency if options else "INR"
        return GroupOut(
            id=group.id,
            plan_id=plan.id,
            title=plan.title,
            request=request,
            status=group.status,
            invite_code=group.invite_code,
            is_owner=me.role == "owner",
            members=[
                MemberOut(
                    user_id=u.id,
                    name=u.full_name,
                    role=m.role,
                    max_budget_per_person=m.max_budget_per_person,
                    votes_cast=sum(1 for v in votes if v.user_id == u.id),
                    is_me=u.id == user.id,
                )
                for m, u in members
            ],
            options=[
                GroupOptionOut(
                    option=by_id[t.option_id],
                    per_person=MoneyOut(amount_minor=t.per_person_minor, currency=currency),
                    love=t.love,
                    ok=t.ok,
                    no=t.no,
                    score=t.score,
                    over_budget_for=t.over_budget,
                    my_vote=mine.get(t.option_id, "none"),
                    position=i + 1,
                )
                for i, t in enumerate(ordered)
            ],
            leader_option_id=leader.option_id if leader else None,
            consensus=explain(leader, len(members), any(t.candidate for t in ordered))
            if leader
            else "No options.",
            decided_option_id=group.decided_option_id,
        )
