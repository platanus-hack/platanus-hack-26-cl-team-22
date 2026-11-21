"""Unit tests for hard filters and soft-filter hooks."""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from travel_sim.application.filters import (
    OptionCriteria,
    RejectionReason,
    apply_hard_filters,
    apply_soft_filters,
    are_options_compatible,
    compute_option_criteria,
    evaluate_hard_filters,
    is_option_eligible,
    local_optimized_scorer,
    make_balanced_substitution_predicate,
    make_max_friction_predicate,
    make_weighted_scorer,
    zero_friction_scorer,
)
from travel_sim.domain import (
    DeviceProfile,
    PaymentMethodPreference,
    ServiceCategory,
    ServiceOption,
    SimType,
    TravelerProfile,
)


def test_esim_only_phone_rejects_physical_sim_option(
    make_option: Callable[..., ServiceOption],
    esim_only_traveler: TravelerProfile,
) -> None:
    physical_opt = make_option(
        id="opt-phys-sim",
        category=ServiceCategory.CONNECTIVITY,
        sim_type=SimType.PHYSICAL_SIM,
    )
    esim_opt = make_option(
        id="opt-esim",
        category=ServiceCategory.CONNECTIVITY,
        sim_type=SimType.ESIM,
    )

    result = apply_hard_filters([physical_opt, esim_opt], esim_only_traveler)

    assert [opt.id for opt in result.eligible] == ["opt-esim"]
    assert len(result.rejected) == 1
    assert result.rejected[0].option.id == "opt-phys-sim"
    assert result.rejected[0].reasons == (RejectionReason.UNSUPPORTED_PHYSICAL_SIM,)


def test_physical_sim_only_phone_rejects_esim_option(
    make_option: Callable[..., ServiceOption],
    physical_sim_only_traveler: TravelerProfile,
) -> None:
    esim_opt = make_option(
        id="opt-esim",
        category=ServiceCategory.CONNECTIVITY,
        sim_type=SimType.ESIM,
    )
    physical_opt = make_option(
        id="opt-phys",
        category=ServiceCategory.CONNECTIVITY,
        sim_type=SimType.PHYSICAL_SIM,
    )

    result = apply_hard_filters([esim_opt, physical_opt], physical_sim_only_traveler)

    assert [opt.id for opt in result.eligible] == ["opt-phys"]
    assert result.rejected[0].reasons == (RejectionReason.UNSUPPORTED_ESIM,)


def test_wifi_only_device_rejects_both_sim_types_but_keeps_non_connectivity(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    traveler = make_traveler(
        device_profile=DeviceProfile(supports_physical_sim=False, supports_esim=False)
    )
    phys = make_option(
        id="phys", category=ServiceCategory.CONNECTIVITY, sim_type=SimType.PHYSICAL_SIM
    )
    esim = make_option(id="esim", category=ServiceCategory.CONNECTIVITY, sim_type=SimType.ESIM)
    transit = make_option(
        id="transit",
        category=ServiceCategory.URBAN_TRANSIT,
        sim_type=SimType.NOT_APPLICABLE,
        data_quota_gb=None,
    )

    result = apply_hard_filters([phys, esim, transit], traveler)
    assert [opt.id for opt in result.eligible] == ["transit"]
    assert {r.option.id: r.reasons for r in result.rejected} == {
        "phys": (RejectionReason.UNSUPPORTED_PHYSICAL_SIM,),
        "esim": (RejectionReason.UNSUPPORTED_ESIM,),
    }


def test_no_local_id_traveler_rejects_rut_only_options(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    tourist = make_traveler(has_local_id=False)
    resident = make_traveler(has_local_id=True)

    rut_only = make_option(id="opt-rut-only", requires_local_id=True)
    open_opt = make_option(id="opt-no-rut", requires_local_id=False)

    tourist_result = apply_hard_filters([rut_only, open_opt], tourist)
    assert [opt.id for opt in tourist_result.eligible] == ["opt-no-rut"]
    assert tourist_result.rejected[0].option.id == "opt-rut-only"
    assert tourist_result.rejected[0].reasons == (RejectionReason.REQUIRES_LOCAL_ID,)

    resident_result = apply_hard_filters([rut_only, open_opt], resident)
    assert [opt.id for opt in resident_result.eligible] == ["opt-rut-only", "opt-no-rut"]
    assert resident_result.rejected == ()


def test_cash_only_traveler_rejects_card_required_option(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    cash_traveler = make_traveler(payment_method_preference=PaymentMethodPreference.CASH_ONLY)
    assert PaymentMethodPreference.CASH_ONLY is PaymentMethodPreference.CASH

    card_only = make_option(
        id="opt-card-only",
        category=ServiceCategory.URBAN_TRANSIT,
        sim_type=SimType.NOT_APPLICABLE,
        data_quota_gb=None,
        requires_international_card=True,
    )
    cash_ok = make_option(
        id="opt-cash-ok",
        category=ServiceCategory.URBAN_TRANSIT,
        sim_type=SimType.NOT_APPLICABLE,
        data_quota_gb=None,
        requires_international_card=False,
    )

    result = apply_hard_filters([card_only, cash_ok], cash_traveler)
    assert [opt.id for opt in result.eligible] == ["opt-cash-ok"]
    assert result.rejected[0].reasons == (RejectionReason.PAYMENT_METHOD_INCOMPATIBLE,)


def test_non_stackable_insufficient_data_quota_is_rejected(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    traveler = make_traveler(trip_duration_days=7, target_data_gb=Decimal(15))
    capped_non_topup = make_option(
        id="opt-no-topup",
        validity_days=30,
        data_quota_gb=Decimal(5),
        allows_top_up=False,
    )
    stackable = make_option(
        id="opt-stackable",
        validity_days=30,
        data_quota_gb=Decimal(5),
        allows_top_up=True,
    )

    result = apply_hard_filters([capped_non_topup, stackable], traveler)
    assert [opt.id for opt in result.eligible] == ["opt-stackable"]
    assert result.rejected[0].reasons == (RejectionReason.INSUFFICIENT_DATA_QUOTA,)


def test_incompatible_options_and_multiple_rejection_reasons(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    traveler = make_traveler(
        destination_city_id="city-test",
        has_local_id=False,
        device_profile=DeviceProfile.esim_only(),
    )
    selected = make_option(id="opt-selected", incompatible_option_ids=frozenset({"opt-conflict"}))
    conflicting = make_option(id="opt-conflict")
    pair_conflict = make_option(id="opt-pair-conflict")
    multi_bad = make_option(
        id="opt-multi-bad",
        city_id="city-other",
        sim_type=SimType.PHYSICAL_SIM,
        requires_local_id=True,
    )

    assert not are_options_compatible(selected, conflicting)
    assert not are_options_compatible(
        selected,
        pair_conflict,
        incompatible_pairs=[("opt-selected", "opt-pair-conflict")],
    )

    assert not is_option_eligible(conflicting, traveler, selected_options=[selected])
    assert evaluate_hard_filters(
        pair_conflict,
        traveler,
        selected_options=[selected],
        incompatible_pairs=[("opt-selected", "opt-pair-conflict")],
    ) == (RejectionReason.INCOMPATIBLE_WITH_SELECTED,)

    multi_reasons = evaluate_hard_filters(multi_bad, traveler)
    assert multi_reasons == (
        RejectionReason.CITY_MISMATCH,
        RejectionReason.UNSUPPORTED_PHYSICAL_SIM,
        RejectionReason.REQUIRES_LOCAL_ID,
    )


def test_soft_filter_scorers_and_predicates(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    traveler = make_traveler(trip_duration_days=5, target_data_gb=Decimal(10))
    zero_opt = make_option(
        id="opt-zero",
        cost_usd_reference=Decimal(40),
        cost_local_currency=Decimal(40000),
        setup_time_minutes=5,
    )
    mid_opt = make_option(
        id="opt-mid",
        cost_usd_reference=Decimal(15),
        cost_local_currency=Decimal(15000),
        setup_time_minutes=20,
        paperwork_level=1,
    )
    hard_local_opt = make_option(
        id="opt-local",
        cost_usd_reference=Decimal(8),
        cost_local_currency=Decimal(8000),
        setup_time_minutes=60,
        paperwork_level=3,
        physical_presence_required=True,
        language_barrier_level=2,
        uncertainty_risk_level=2,
    )
    candidates = [hard_local_opt, zero_opt, mid_opt]

    # Extra time T is measured relative to the minimum-friction option (opt-zero, 5 min).
    criteria_by_id = {c.option.id: c for c in compute_option_criteria(candidates, traveler)}
    assert criteria_by_id["opt-zero"].extra_time_minutes == 0
    assert criteria_by_id["opt-mid"].extra_time_minutes == 15
    assert criteria_by_id["opt-local"].extra_time_minutes == 55

    zf_ranked = apply_soft_filters(candidates, traveler, scorer=zero_friction_scorer)
    assert [s.criteria.option.id for s in zf_ranked] == ["opt-zero", "opt-mid", "opt-local"]

    local_ranked = apply_soft_filters(candidates, traveler, scorer=local_optimized_scorer)
    assert [s.criteria.option.id for s in local_ranked] == ["opt-local", "opt-mid", "opt-zero"]

    # Balanced substitution hook: opt-mid saves $25 for ~15.83 friction pts (> $0.75/pt, <= 50),
    # while opt-local has friction 100 (> 50 max threshold).
    balanced_pred = make_balanced_substitution_predicate(
        criteria_by_id["opt-zero"],
        min_usd_per_friction_point=Decimal("0.75"),
        max_friction=Decimal(50),
    )
    balanced = apply_soft_filters(
        candidates,
        traveler,
        scorer=local_optimized_scorer,
        predicates=[balanced_pred],
    )
    assert [s.criteria.option.id for s in balanced] == ["opt-mid"]

    # Max-friction predicate + custom weighted hook.
    weighted = apply_soft_filters(
        candidates,
        traveler,
        scorer=make_weighted_scorer(cost_weight=1, friction_weight=1, extra_time_weight="0.5"),
        predicates=[make_max_friction_predicate(Decimal(50))],
    )
    assert [s.criteria.option.id for s in weighted] == ["opt-mid", "opt-zero"]


def test_custom_soft_filter_hook_protocol(
    make_option: Callable[..., ServiceOption],
    make_traveler: Callable[..., TravelerProfile],
) -> None:
    traveler = make_traveler()
    opt_a = make_option(id="a", cost_usd_reference=Decimal(10))
    opt_b = make_option(id="b", cost_usd_reference=Decimal(20))

    def custom_scorer(criteria: OptionCriteria, _traveler: TravelerProfile) -> Decimal:
        return -criteria.total_cost_usd

    ranked = apply_soft_filters([opt_a, opt_b], traveler, scorer=custom_scorer)
    assert [s.criteria.option.id for s in ranked] == ["b", "a"]
