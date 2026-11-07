"""Group consensus: a transparent, deterministic rule (no AI).

Each member marks options Love (+2), OK (+1) or No (veto, -2). An option is a candidate when
nobody vetoed it and it fits every member's per-person budget. Candidates are ranked by total
score, then by how many members voted, then by the planner's own rank. If no option is a
candidate, the least-objectionable one leads (fewest vetoes, then fewest budget conflicts), and
the explanation says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VOTE_VALUES = {"love": 2, "ok": 1, "no": -2}
VOTE_NAMES = {v: k for k, v in VOTE_VALUES.items()}


@dataclass
class OptionTally:
    option_id: str
    plan_rank: int
    per_person_minor: int
    love: int = 0
    ok: int = 0
    no: int = 0
    over_budget: list[str] = field(default_factory=list)  # member names it is too expensive for

    @property
    def score(self) -> int:
        return 2 * self.love + self.ok - 2 * self.no

    @property
    def voters(self) -> int:
        return self.love + self.ok + self.no

    @property
    def candidate(self) -> bool:
        return self.no == 0 and not self.over_budget


def rank(tallies: list[OptionTally]) -> list[OptionTally]:
    return sorted(
        tallies,
        key=lambda t: (
            not t.candidate,
            t.no,
            len(t.over_budget),
            -t.score,
            -t.voters,
            t.plan_rank,
        ),
    )


def explain(leader: OptionTally, members: int, any_candidate: bool) -> str:
    votes = f"{leader.voters} of {members} voted: {leader.love} love, {leader.ok} OK" + (
        f", {leader.no} no" if leader.no else ""
    )
    if not leader.voters:
        return "Nobody has voted yet; the planner's top pick leads for now."
    if leader.candidate:
        return f"{votes}. No vetoes and it fits everyone's budget."
    reasons = []
    if leader.no:
        reasons.append(f"{leader.no} veto{'es' if leader.no > 1 else ''}")
    if leader.over_budget:
        reasons.append(f"over budget for {', '.join(leader.over_budget)}")
    prefix = (
        "Every option has an objection, so this one leads with the fewest"
        if (not any_candidate)
        else "Leading"
    )
    return f"{prefix} ({'; '.join(reasons)}). {votes}."
