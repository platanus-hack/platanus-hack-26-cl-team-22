"""Domain value objects for the deterministic travel cost-vs-friction engine."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from travel_sim.domain.enums import SimType

NumericInput = Decimal | int | str | float


def to_decimal(value: NumericInput, field_name: str) -> Decimal:
    """Convert a numeric value to a finite Decimal without binary float drift."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not bool")
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, (str, float)):
        try:
            dec = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"{field_name} is not a valid decimal number: {value!r}") from exc
    else:
        raise TypeError(f"{field_name} must be Decimal, int, str, or float")

    if not dec.is_finite():
        raise ValueError(f"{field_name} must be finite, got {value!r}")
    return dec


@dataclass(frozen=True, slots=True)
class Money:
    """Exact monetary amount tagged with an ISO 4217 currency code."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        dec = to_decimal(self.amount, "amount")
        code = self.currency.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError(f"currency must be a 3-letter ISO 4217 code, got {self.currency!r}")
        object.__setattr__(self, "amount", dec)
        object.__setattr__(self, "currency", code)

    def _require_same_currency(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise TypeError(f"expected Money, got {type(other).__name__}")
        if self.currency != other.currency:
            raise ValueError(
                f"cannot operate on mismatched currencies: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: NumericInput) -> Money:
        return Money(self.amount * to_decimal(factor, "factor"), self.currency)

    def __rmul__(self, factor: NumericInput) -> Money:
        return self.__mul__(factor)

    def __truediv__(self, divisor: NumericInput) -> Money:
        div = to_decimal(divisor, "divisor")
        if div == 0:
            raise ZeroDivisionError("cannot divide Money by zero")
        return Money(self.amount / div, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount >= other.amount


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """Hardware SIM capabilities of the traveler's phone."""

    supports_physical_sim: bool
    supports_esim: bool

    def __post_init__(self) -> None:
        if not isinstance(self.supports_physical_sim, bool):
            raise TypeError("supports_physical_sim must be a bool")
        if not isinstance(self.supports_esim, bool):
            raise TypeError("supports_esim must be a bool")

    def supports_sim_type(self, sim_type: SimType) -> bool:
        """Return True if this device can use the given SIM format."""
        if sim_type == SimType.PHYSICAL_SIM:
            return self.supports_physical_sim
        if sim_type == SimType.ESIM:
            return self.supports_esim
        return True

    @classmethod
    def esim_only(cls) -> DeviceProfile:
        """Device with eSIM support and no physical SIM tray."""
        return cls(supports_physical_sim=False, supports_esim=True)

    @classmethod
    def physical_sim_only(cls) -> DeviceProfile:
        """Device with a physical SIM slot and no eSIM support."""
        return cls(supports_physical_sim=True, supports_esim=False)

    @classmethod
    def dual_sim(cls) -> DeviceProfile:
        """Device supporting both physical SIM and eSIM."""
        return cls(supports_physical_sim=True, supports_esim=True)


@dataclass(frozen=True, slots=True)
class FrictionScore:
    """Decomposed operational friction score bounded to [0, 100]."""

    value: Decimal
    setup_time: Decimal
    paperwork: Decimal
    physical_presence: Decimal
    language_barrier: Decimal
    uncertainty_risk: Decimal

    def __post_init__(self) -> None:
        for field_name in (
            "value",
            "setup_time",
            "paperwork",
            "physical_presence",
            "language_barrier",
            "uncertainty_risk",
        ):
            dec = to_decimal(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, dec)

        if not (Decimal(0) <= self.value <= Decimal(100)):
            raise ValueError(f"friction score value must be in [0, 100], got {self.value}")
