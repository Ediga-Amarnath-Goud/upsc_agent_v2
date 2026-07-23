import math
import json


def get_k_factor(total_attempted: int) -> int:
    if total_attempted < 30:
        return 40
    elif total_attempted < 100:
        return 25
    elif total_attempted < 300:
        return 15
    return 10


def get_question_rating(difficulty_tier: int) -> int:
    tier = max(1, min(10, difficulty_tier))
    return 800 + (tier * 100)


def get_expected_score(student_elo: int, question_rating: int) -> float:
    return 1.0 / (1.0 + math.pow(10, (question_rating - student_elo) / 400.0))


def compute_elo_update(current_elo: int, difficulty_tier: int, correct: bool, total_attempted: int) -> tuple[int, int]:
    q_rating = get_question_rating(difficulty_tier)
    expected = get_expected_score(current_elo, q_rating)
    k = get_k_factor(total_attempted)
    actual = 1.0 if correct else 0.0
    delta = round(k * (actual - expected))
    new_elo = max(400, min(2000, current_elo + delta))
    delta_actual = new_elo - current_elo
    return new_elo, delta_actual


def update_trap_stats(trap_stats: dict, trap_type: str, correct: bool) -> dict:
    stats = trap_stats.get(trap_type, {"encountered": 0, "correct": 0, "wrong": 0})
    stats["encountered"] += 1
    if correct:
        stats["correct"] += 1
    else:
        stats["wrong"] += 1
    trap_stats[trap_type] = stats
    return trap_stats


def _calculate_trajectory(last_5: list[int]) -> str:
    if len(last_5) < 3:
        return "insufficient"
    recent_acc = sum(last_5) / len(last_5)
    if recent_acc >= 0.8:
        return "up"
    elif recent_acc <= 0.2:
        return "down"
    return "flat"


def update_subject_trap_accuracy(
    st_accuracy: dict, subject: str, trap_type: str, correct: bool
) -> dict:
    if subject not in st_accuracy:
        st_accuracy[subject] = {}
    subj = st_accuracy[subject]
    if trap_type not in subj:
        subj[trap_type] = {"encountered": 0, "correct": 0, "last_5": [], "trajectory": "insufficient"}
    cell = subj[trap_type]
    cell["encountered"] += 1
    if correct:
        cell["correct"] += 1
    cell["last_5"].append(1 if correct else 0)
    if len(cell["last_5"]) > 5:
        cell["last_5"] = cell["last_5"][-5:]
    cell["trajectory"] = _calculate_trajectory(cell["last_5"])
    return st_accuracy


def get_weakest_traps(
    subject_trap_accuracy: dict,
    trap_stats: dict,
    min_encountered: int = 3
) -> list[tuple[str, str, float]]:
    scored = []
    for subject, traps in subject_trap_accuracy.items():
        for trap_type, cell in traps.items():
            if cell["encountered"] < min_encountered:
                continue
            acc = cell["correct"] / cell["encountered"]
            weakness = (1.0 - acc) * math.log(cell["encountered"] + 1)
            trajectory_penalty = 0.0
            if cell["trajectory"] == "down":
                trajectory_penalty = weakness * 0.3
            elif cell["trajectory"] == "up":
                trajectory_penalty = -weakness * 0.2
            scored.append((subject, trap_type, round(weakness + trajectory_penalty, 4)))
    for trap_type, stats in trap_stats.items():
        already_tracked = any(t == trap_type for _, t, _ in scored)
        if already_tracked:
            continue
        if stats["encountered"] < min_encountered:
            continue
        acc = stats["correct"] / stats["encountered"]
        weakness = (1.0 - acc) * math.log(stats["encountered"] + 1)
        scored.append(("GLOBAL", trap_type, round(weakness, 4)))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored


def get_priority_matrix(
    student: any,
    count: int = 10,
    topic: str | None = None
) -> list[dict]:
    st_accuracy = student.subject_trap_accuracy or {}
    t_stats = student.trap_stats or {}
    weakest = get_weakest_traps(st_accuracy, t_stats)
    subj_elos = student.subject_elos or {}
    global_elo = student.current_elo or 1200
    plan = []
    n_weak = max(1, round(count * 0.6))
    n_other = max(1, round(count * 0.3))
    n_maintain = count - n_weak - n_other
    for item in weakest[:n_weak]:
        subject, trap_type, _ = item
        subject_elo = subj_elos.get(subject, global_elo)
        base_diff = max(1, min(10, round((subject_elo - 800) / 100)))
        plan.append({
            "slot": len(plan) + 1,
            "subject": subject,
            "trap": trap_type,
            "difficulty_tier": max(1, base_diff - 1),
            "reason": "weak"
        })
    remaining_traps = [t for t in get_all_trap_types(st_accuracy, t_stats) if t not in [x[1] for x in weakest[:n_weak]]]
    for trap_type in remaining_traps[:n_other]:
        plan.append({
            "slot": len(plan) + 1,
            "subject": next(iter(subj_elos.keys())) if subj_elos else "GS1",
            "trap": trap_type,
            "difficulty_tier": max(1, min(10, round((global_elo - 800) / 100))),
            "reason": "maintenance"
        })
    for i in range(n_maintain):
        if weakest and len(weakest) > 0:
            best = weakest[-1]
            subject, trap_type, _ = best
            subject_elo = subj_elos.get(subject, global_elo)
            plan.append({
                "slot": len(plan) + 1,
                "subject": subject,
                "trap": trap_type,
                "difficulty_tier": max(1, min(10, round((subject_elo - 700) / 100))),
                "reason": "confidence"
            })
    return plan[:count]


def get_all_trap_types(subject_trap_accuracy: dict, trap_stats: dict) -> list[str]:
    types = set()
    for subject, traps in subject_trap_accuracy.items():
        for trap_type in traps:
            types.add(trap_type)
    for trap_type in trap_stats:
        types.add(trap_type)
    return list(types)
