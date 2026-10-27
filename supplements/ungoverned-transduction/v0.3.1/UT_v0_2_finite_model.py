#!/usr/bin/env python3
"""Ungoverned Transduction v0.2: deterministic, synthetic finite-case witness.

Research artifact only. Encoded policy is stipulated, not an enterprise security test.
Version: v0.2 / 2026-10-27. Requires Python >= 3.9, standard library only.
Command: python3 UT_v0_2_finite_model.py
"""
from dataclasses import dataclass
from typing import Optional
import csv
from pathlib import Path

Tri = Optional[bool]  # True, False, None = necessary record unavailable


def tri_and(*values: Tri) -> Tri:
    """Known violation dominates unknown; otherwise unknown dominates pass."""
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


@dataclass(frozen=True)
class Case:
    name: str
    invoked: bool
    effect: Optional[bool]
    adequate_window: bool
    stage_write_permission: Tri
    service_api_permission: Tri
    status_admission: Tri
    status_semantics: Tri
    effect_mandate: Tri
    evidence_sufficiency: Tri
    enforcement: bool
    value_units: Optional[float] = None

    @property
    def local(self) -> Tri:
        return tri_and(self.stage_write_permission, self.service_api_permission)

    @property
    def end_to_end(self) -> Tri:
        return tri_and(self.stage_write_permission, self.service_api_permission,
                       self.status_admission, self.status_semantics, self.effect_mandate,
                       self.evidence_sufficiency)

    @property
    def strong_baseline(self) -> str:
        decision = self.end_to_end
        return 'PERMIT' if decision is True else ('DENY' if decision is False else 'HOLD')

    @property
    def verdict(self) -> str:
        if not self.invoked:
            return 'OUT_OF_SCOPE'
        if not self.adequate_window or self.effect is None:
            return 'NON_EVALUABLE_EFFECT'
        if self.effect is False:
            return 'NON_TRANSDUCTION_IN_WINDOW'
        decision = self.end_to_end
        return ('ADMISSIBLE_EFFECT' if decision is True else
                'UNGOVERNED_EFFECT' if decision is False else
                'NON_EVALUABLE_GUARD')


CASES = (
    Case('W1_status_laundering', True, True, True,
         True, True, True, False, False, True, False),
    Case('P1_valid_authorized_but_loss', True, True, True,
         True, True, True, True, True, True, True, -5.0),
    Case('B1_strong_PEP_blocks', True, False, True,
         True, True, True, False, False, True, True),
    Case('N1_no_effect_within_window', True, False, True,
         True, True, True, True, True, True, False),
    Case('U1_missing_mandate_record', True, True, True,
         True, True, True, True, None, True, False),
    Case('F1_insufficient_evidence', True, True, True,
         True, True, True, True, True, False, False),
    Case('U2_missing_effect_record', True, None, True,
         True, True, True, True, True, True, False),
    Case('O1_no_invocation', False, False, True,
         True, True, True, True, True, True, False),
)

EXPECTED = {
    'W1_status_laundering': ('UNGOVERNED_EFFECT', 'DENY'),
    'P1_valid_authorized_but_loss': ('ADMISSIBLE_EFFECT', 'PERMIT'),
    'B1_strong_PEP_blocks': ('NON_TRANSDUCTION_IN_WINDOW', 'DENY'),
    'N1_no_effect_within_window': ('NON_TRANSDUCTION_IN_WINDOW', 'PERMIT'),
    'U1_missing_mandate_record': ('NON_EVALUABLE_GUARD', 'HOLD'),
    'F1_insufficient_evidence': ('UNGOVERNED_EFFECT', 'DENY'),
    'U2_missing_effect_record': ('NON_EVALUABLE_EFFECT', 'PERMIT'),
    'O1_no_invocation': ('OUT_OF_SCOPE', 'PERMIT'),
}


def main():
    assert len({c.name for c in CASES}) == len(CASES)
    for case in CASES:
        assert (case.verdict, case.strong_baseline) == EXPECTED[case.name], case.name
        if case.enforcement and case.invoked and case.end_to_end is not True:
            assert case.effect is False, f'fully enforced PEP must block {case.name}'

    witness = CASES[0]
    assert witness.local is True and witness.end_to_end is False
    control = CASES[1]
    assert control.local is True and control.end_to_end is True
    assert control.value_units < 0  # admissible does not imply positive value
    # Under the fully specified baseline, the same W1 defect is rejected:
    assert witness.strong_baseline == 'DENY'
    # Monotonic three-valued aggregation under missing/known-fail evidence:
    assert tri_and(True, None) is None and tri_and(None, False) is False

    output = Path(__file__).with_name('UT_v0_2_finite_cases.csv')
    with output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['case_id','invoked','effect','adequate_window','local_guard',
                         'end_to_end_guard','baseline_decision','verdict','value_units'])
        for c in CASES:
            writer.writerow([c.name, c.invoked, c.effect, c.adequate_window,
                             c.local, c.end_to_end, c.strong_baseline,
                             c.verdict, c.value_units])
    for c in CASES:
        print(f'{c.name}: local={c.local}, global={c.end_to_end}, '
              f'baseline={c.strong_baseline}, verdict={c.verdict}')
    print('PASS: 8 declared synthetic cases, local/global witness, positive control, '
          'negative-value case, and strong-baseline blocking check.')
    print(f'CSV: {output}')


if __name__ == '__main__':
    main()
