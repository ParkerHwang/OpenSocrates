"""Reproduce a synthetic counterexample; this is not OpenSocrates runtime code."""

from fractions import Fraction


def percent(numerator: int, denominator: int) -> str:
    return f"{float(Fraction(numerator, denominator)) * 100:.2f}%"


def main() -> None:
    # All IDs and cohorts are invented for this example. Both scenarios have
    # exactly the same monthly totals; only the identity overlap changes.
    cohorts = {
        "A": (100, 80, 70),
        "B": (10, 9, 8),
    }
    for scenario in ("nested", "reactivation"):
        initial = month1 = month2 = overlap = 0
        for size, m1_count, m2_count in cohorts.values():
            first = set(range(1, m1_count + 1))
            if scenario == "nested":
                second = set(range(1, m2_count + 1))
            else:
                second = set(range(size - m2_count + 1, size + 1))
            initial += size
            month1 += len(first)
            month2 += len(second)
            overlap += len(first & second)
        print(
            f"{scenario}: initial={initial}, month1={month1}, month2={month2}, "
            f"overlap={overlap}, month1/initial={percent(month1, initial)}, "
            f"month2/initial={percent(month2, initial)}, "
            f"month2/month1 counts={percent(month2, month1)}, "
            f"month1-to-month2 retained={percent(overlap, month1)}"
        )


if __name__ == "__main__":
    main()
