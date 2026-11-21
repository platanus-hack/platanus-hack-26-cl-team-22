"""City-agnostic JSON repository adapter implementing OptionRepository port."""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from travel_sim.application.ports import OptionRepository
from travel_sim.domain import (
    City,
    FreshnessStatus,
    PricingModel,
    ServiceCategory,
    ServiceOption,
    SimType,
    freshness_status,
)

_REQUIRED_OPTION_FIELDS: tuple[str, ...] = (
    "id",
    "city_id",
    "category",
    "provider",
    "name",
    "cost_local_currency",
    "cost_usd_reference",
    "pricing_model",
    "validity_days",
    "setup_time_minutes",
    "paperwork_level",
    "language_barrier_level",
    "physical_presence_required",
    "uncertainty_risk_level",
    "requires_local_id",
    "sim_type",
    "is_tourist_friendly",
)

_REQUIRED_CITY_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "country_code",
    "local_currency",
    "default_usd_exchange_rate",
)


class RepositoryValidationError(ValueError):
    """Raised when repository input data fails strict schema or domain validation."""


class JsonOptionRepository(OptionRepository):
    """City-agnostic JSON-backed repository implementation for travel options."""

    def __init__(
        self,
        data_source: str | Path | Sequence[str | Path] | None = None,
    ) -> None:
        self._cities: dict[str, City] = {}
        self._options: dict[str, ServiceOption] = {}
        self._unverified_option_ids: set[str] = set()
        self._city_options: dict[str, list[str]] = defaultdict(list)

        if data_source is not None:
            if isinstance(data_source, (str, Path)):
                path = Path(data_source)
                if path.is_dir():
                    self.load_directory(path)
                elif path.is_file():
                    self.load_file(path)
                else:
                    raise FileNotFoundError(f"Path does not exist: {path}")
            elif isinstance(data_source, Sequence):
                for item in data_source:
                    p = Path(item)
                    if p.is_dir():
                        self.load_directory(p)
                    elif p.is_file():
                        self.load_file(p)
                    else:
                        raise FileNotFoundError(f"Path does not exist: {p}")

    def load_directory(self, dir_path: str | Path) -> None:
        """Load all JSON files in dir_path in deterministic sorted order."""
        directory = Path(dir_path)
        if not directory.is_dir():
            raise NotADirectoryError(f"Directory does not exist: {directory}")
        for json_file in sorted(directory.glob("*.json")):
            self.load_file(json_file)

    def load_file(self, file_path: str | Path) -> None:
        """Load and validate city dataset from a single JSON file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Seed file not found: {path}")
        with path.open("r", encoding="utf-8") as file:
            try:
                payload = json.load(file)
            except json.JSONDecodeError as exc:
                raise RepositoryValidationError(f"Invalid JSON in {path}: {exc}") from exc
        self.load_dict(payload, source=str(path))

    def load_dict(self, payload: object, *, source: str = "<memory>") -> None:
        """Strictly validate and register city and option records from dictionary."""
        if not isinstance(payload, dict):
            raise RepositoryValidationError(
                f"Root element in {source} must be a JSON object, got {type(payload).__name__}"
            )

        city = self._validate_and_build_city(payload, source=source)
        options = self._validate_and_build_options(payload, city_id=city.id, source=source)

        seen_in_payload: set[str] = set()
        for option, _ in options:
            if option.id in seen_in_payload:
                raise RepositoryValidationError(
                    f"Duplicate option id '{option.id}' within {source}"
                )
            if option.id in self._options:
                raise RepositoryValidationError(
                    f"Duplicate option id '{option.id}' in {source} (already registered)"
                )
            seen_in_payload.add(option.id)

        self._cities[city.id] = city
        for option, is_unverified in options:
            self._options[option.id] = option
            if is_unverified:
                self._unverified_option_ids.add(option.id)
            if option.id not in self._city_options[option.city_id]:
                self._city_options[option.city_id].append(option.id)

    def _validate_and_build_city(self, payload: dict[str, object], *, source: str) -> City:
        city_raw: object = payload.get("city")
        if city_raw is None:
            if all(key in payload for key in _REQUIRED_CITY_FIELDS) and "options" in payload:
                city_raw = payload
            else:
                raise RepositoryValidationError(
                    f"Missing 'city' definition or required city fields in {source}"
                )

        if not isinstance(city_raw, dict):
            raise RepositoryValidationError(f"'city' in {source} must be an object")

        for req_field in _REQUIRED_CITY_FIELDS:
            if req_field not in city_raw or city_raw[req_field] is None:
                raise RepositoryValidationError(
                    f"Missing required city field '{req_field}' in {source}"
                )

        city_id = str(city_raw["id"]).strip()
        name = str(city_raw["name"]).strip()
        country_code = str(city_raw["country_code"]).strip().upper()
        local_currency = str(city_raw["local_currency"]).strip().upper()

        if not city_id:
            raise RepositoryValidationError(f"City id cannot be empty in {source}")
        if not name:
            raise RepositoryValidationError(f"City name cannot be empty in {source}")
        if len(country_code) != 2 or not country_code.isalpha():
            raise RepositoryValidationError(
                f"country_code must be a 2-letter ISO 3166-1 code, got {country_code!r} in {source}"
            )
        if len(local_currency) != 3 or not local_currency.isalpha():
            raise RepositoryValidationError(
                f"local_currency must be a 3-letter ISO 4217 code, got {local_currency!r} in {source}"
            )

        try:
            exchange_rate = Decimal(str(city_raw["default_usd_exchange_rate"]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RepositoryValidationError(
                f"Invalid default_usd_exchange_rate in {source}"
            ) from exc

        if exchange_rate <= 0:
            raise RepositoryValidationError(
                f"default_usd_exchange_rate must be > 0, got {exchange_rate} in {source}"
            )

        city_lva = city_raw.get("last_verified_at")
        if city_lva is not None:
            if not isinstance(city_lva, str) or not city_lva.strip():
                raise RepositoryValidationError(
                    f"City last_verified_at must be an ISO 8601 string or null in {source}"
                )
            try:
                datetime.fromisoformat(city_lva)
            except ValueError as exc:
                raise RepositoryValidationError(
                    f"City last_verified_at has invalid ISO date '{city_lva}' in {source}"
                ) from exc

            return City(
                id=city_id,
                name=name,
                country_code=country_code,
                local_currency=local_currency,
                default_usd_exchange_rate=exchange_rate,
                last_verified_at=city_lva,
            )

        # last_verified_at is null: construct unverified City instance
        city_obj = object.__new__(City)
        object.__setattr__(city_obj, "id", city_id)
        object.__setattr__(city_obj, "name", name)
        object.__setattr__(city_obj, "country_code", country_code)
        object.__setattr__(city_obj, "local_currency", local_currency)
        object.__setattr__(city_obj, "default_usd_exchange_rate", exchange_rate)
        object.__setattr__(city_obj, "last_verified_at", None)
        return city_obj

    def _validate_and_build_options(
        self,
        payload: dict[str, object],
        *,
        city_id: str,
        source: str,
    ) -> list[tuple[ServiceOption, bool]]:
        options_raw = payload.get("options")
        if options_raw is None:
            raise RepositoryValidationError(f"Missing 'options' field in {source}")
        if not isinstance(options_raw, list):
            raise RepositoryValidationError(f"'options' in {source} must be a list")

        results: list[tuple[ServiceOption, bool]] = []
        for index, raw_item in enumerate(options_raw):
            if not isinstance(raw_item, dict):
                raise RepositoryValidationError(
                    f"Option at index {index} in {source} must be an object"
                )

            opt, is_unverified = self._validate_single_option(
                raw_item, default_city_id=city_id, source=source, index=index
            )
            results.append((opt, is_unverified))

        return results

    def _validate_single_option(
        self,
        raw: dict[str, object],
        *,
        default_city_id: str,
        source: str,
        index: int,
    ) -> tuple[ServiceOption, bool]:
        opt_id_raw = raw.get("id")
        opt_id = str(opt_id_raw).strip() if opt_id_raw is not None else f"index-{index}"

        for req_field in _REQUIRED_OPTION_FIELDS:
            if req_field not in raw or raw[req_field] is None:
                raise RepositoryValidationError(
                    f"Missing required field '{req_field}' in option '{opt_id}' ({source})"
                )

        if not str(raw["id"]).strip():
            raise RepositoryValidationError(f"Option id cannot be empty ({source})")

        opt_city_id = str(raw["city_id"]).strip()
        if not opt_city_id:
            opt_city_id = default_city_id

        # Enum validations
        category_raw = raw["category"]
        try:
            category = ServiceCategory(str(category_raw))
        except ValueError as exc:
            allowed = ", ".join(c.value for c in ServiceCategory)
            raise RepositoryValidationError(
                f"Unknown ServiceCategory '{category_raw}' in option '{opt_id}'. "
                f"Allowed values: {allowed}"
            ) from exc

        pricing_model_raw = raw["pricing_model"]
        try:
            pricing_model = PricingModel(str(pricing_model_raw))
        except ValueError as exc:
            allowed = ", ".join(p.value for p in PricingModel)
            raise RepositoryValidationError(
                f"Unknown PricingModel '{pricing_model_raw}' in option '{opt_id}'. "
                f"Allowed values: {allowed}"
            ) from exc

        sim_type_raw = raw["sim_type"]
        try:
            sim_type = SimType(str(sim_type_raw))
        except ValueError as exc:
            allowed = ", ".join(s.value for s in SimType)
            raise RepositoryValidationError(
                f"Unknown SimType '{sim_type_raw}' in option '{opt_id}'. "
                f"Allowed values: {allowed}"
            ) from exc

        if category == ServiceCategory.CONNECTIVITY and sim_type not in (
            SimType.PHYSICAL_SIM,
            SimType.ESIM,
        ):
            raise RepositoryValidationError(
                f"CONNECTIVITY option '{opt_id}' requires sim_type PHYSICAL_SIM or ESIM, "
                f"got '{sim_type.value}'"
            )

        provider = str(raw["provider"]).strip()
        if not provider:
            raise RepositoryValidationError(f"provider cannot be empty in option '{opt_id}'")

        name = str(raw["name"]).strip()
        if not name:
            raise RepositoryValidationError(f"name cannot be empty in option '{opt_id}'")

        # Monetary validations
        try:
            cost_local = Decimal(str(raw["cost_local_currency"]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RepositoryValidationError(
                f"Invalid cost_local_currency in option '{opt_id}'"
            ) from exc
        if cost_local < 0:
            raise RepositoryValidationError(
                f"cost_local_currency cannot be negative in option '{opt_id}', got {cost_local}"
            )

        try:
            cost_usd = Decimal(str(raw["cost_usd_reference"]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RepositoryValidationError(
                f"Invalid cost_usd_reference in option '{opt_id}'"
            ) from exc
        if cost_usd < 0:
            raise RepositoryValidationError(
                f"cost_usd_reference cannot be negative in option '{opt_id}', got {cost_usd}"
            )

        # Integer range validations
        for int_field, min_val, max_val in (
            ("validity_days", 1, None),
            ("setup_time_minutes", 0, None),
            ("paperwork_level", 0, 3),
            ("language_barrier_level", 0, 2),
            ("uncertainty_risk_level", 0, 2),
        ):
            val = raw[int_field]
            if isinstance(val, bool) or not isinstance(val, int):
                raise RepositoryValidationError(
                    f"Field '{int_field}' in option '{opt_id}' must be an int, got {type(val).__name__}"
                )
            if val < min_val or (max_val is not None and val > max_val):
                bound = f"[{min_val}, {max_val}]" if max_val is not None else f">= {min_val}"
                raise RepositoryValidationError(
                    f"Field '{int_field}' in option '{opt_id}' must be {bound}, got {val}"
                )

        # Boolean validations
        for bool_field in (
            "physical_presence_required",
            "requires_local_id",
            "is_tourist_friendly",
        ):
            b_val = raw[bool_field]
            if not isinstance(b_val, bool):
                raise RepositoryValidationError(
                    f"Field '{bool_field}' in option '{opt_id}' must be a bool, got {type(b_val).__name__}"
                )

        req_card = raw.get("requires_international_card", False)
        if not isinstance(req_card, bool):
            raise RepositoryValidationError(
                f"Field 'requires_international_card' in option '{opt_id}' must be a bool"
            )

        allows_top_up = raw.get("allows_top_up", True)
        if not isinstance(allows_top_up, bool):
            raise RepositoryValidationError(
                f"Field 'allows_top_up' in option '{opt_id}' must be a bool"
            )

        # Optional data quota validation
        data_quota_raw = raw.get("data_quota_gb")
        if data_quota_raw is not None:
            try:
                data_quota_gb = Decimal(str(data_quota_raw))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise RepositoryValidationError(
                    f"Invalid data_quota_gb in option '{opt_id}'"
                ) from exc
            if data_quota_gb < 0:
                raise RepositoryValidationError(
                    f"data_quota_gb cannot be negative in option '{opt_id}', got {data_quota_gb}"
                )
        else:
            data_quota_gb = None

        # Freshness / verification validation
        lva_raw = raw.get("last_verified_at")
        is_unverified = False
        if lva_raw is None:
            is_unverified = True
            last_verified_at_str = None
        elif isinstance(lva_raw, str):
            if not lva_raw.strip():
                raise RepositoryValidationError(
                    f"Empty last_verified_at string in option '{opt_id}'. Use null for unverified."
                )
            try:
                datetime.fromisoformat(lva_raw)
            except ValueError as exc:
                raise RepositoryValidationError(
                    f"Invalid ISO 8601 date for 'last_verified_at' in option '{opt_id}': '{lva_raw}'"
                ) from exc
            last_verified_at_str = lva_raw.strip()
        else:
            raise RepositoryValidationError(
                f"last_verified_at in option '{opt_id}' must be an ISO 8601 string or null, "
                f"got {type(lva_raw).__name__}"
            )

        source_url_raw = raw.get("verification_source_url")
        if source_url_raw is None:
            source_url = ""
        elif isinstance(source_url_raw, str):
            source_url = source_url_raw.strip()
        else:
            raise RepositoryValidationError(
                f"verification_source_url in option '{opt_id}' must be a string"
            )

        if last_verified_at_str is None or not source_url:
            is_unverified = True

        notes = str(raw.get("notes") or "")
        incompatible_raw = raw.get("incompatible_option_ids") or []
        if isinstance(incompatible_raw, str) or not hasattr(incompatible_raw, "__iter__"):
            raise RepositoryValidationError(
                f"incompatible_option_ids in option '{opt_id}' must be an iterable of string IDs"
            )
        incompatible_set = frozenset(str(x) for x in incompatible_raw)

        if last_verified_at_str is not None:
            option_instance = ServiceOption(
                id=str(raw["id"]).strip(),
                city_id=opt_city_id,
                category=category,
                provider=provider,
                name=name,
                cost_local_currency=cost_local,
                cost_usd_reference=cost_usd,
                pricing_model=pricing_model,
                validity_days=int(raw["validity_days"]),
                data_quota_gb=data_quota_gb,
                setup_time_minutes=int(raw["setup_time_minutes"]),
                paperwork_level=int(raw["paperwork_level"]),
                language_barrier_level=int(raw["language_barrier_level"]),
                physical_presence_required=bool(raw["physical_presence_required"]),
                uncertainty_risk_level=int(raw["uncertainty_risk_level"]),
                requires_local_id=bool(raw["requires_local_id"]),
                sim_type=sim_type,
                is_tourist_friendly=bool(raw["is_tourist_friendly"]),
                last_verified_at=last_verified_at_str,
                verification_source_url=source_url,
                notes=notes,
                requires_international_card=req_card,
                allows_top_up=allows_top_up,
                incompatible_option_ids=incompatible_set,
            )
        else:
            # Unverified option: last_verified_at is None
            option_instance = object.__new__(ServiceOption)
            object.__setattr__(option_instance, "id", str(raw["id"]).strip())
            object.__setattr__(option_instance, "city_id", opt_city_id)
            object.__setattr__(option_instance, "category", category)
            object.__setattr__(option_instance, "provider", provider)
            object.__setattr__(option_instance, "name", name)
            object.__setattr__(option_instance, "cost_local_currency", cost_local)
            object.__setattr__(option_instance, "cost_usd_reference", cost_usd)
            object.__setattr__(option_instance, "pricing_model", pricing_model)
            object.__setattr__(option_instance, "validity_days", int(raw["validity_days"]))
            object.__setattr__(option_instance, "data_quota_gb", data_quota_gb)
            object.__setattr__(
                option_instance, "setup_time_minutes", int(raw["setup_time_minutes"])
            )
            object.__setattr__(option_instance, "paperwork_level", int(raw["paperwork_level"]))
            object.__setattr__(
                option_instance, "language_barrier_level", int(raw["language_barrier_level"])
            )
            object.__setattr__(
                option_instance,
                "physical_presence_required",
                bool(raw["physical_presence_required"]),
            )
            object.__setattr__(
                option_instance, "uncertainty_risk_level", int(raw["uncertainty_risk_level"])
            )
            object.__setattr__(
                option_instance, "requires_local_id", bool(raw["requires_local_id"])
            )
            object.__setattr__(option_instance, "sim_type", sim_type)
            object.__setattr__(
                option_instance, "is_tourist_friendly", bool(raw["is_tourist_friendly"])
            )
            object.__setattr__(option_instance, "last_verified_at", None)
            object.__setattr__(option_instance, "verification_source_url", source_url)
            object.__setattr__(option_instance, "notes", notes)
            object.__setattr__(option_instance, "requires_international_card", req_card)
            object.__setattr__(option_instance, "allows_top_up", allows_top_up)
            object.__setattr__(option_instance, "incompatible_option_ids", incompatible_set)

        return option_instance, is_unverified

    # OptionRepository Port Implementation

    def list_cities(self) -> Sequence[City]:
        """List all available destination cities in deterministic order."""
        return tuple(self._cities.values())

    def get_city(self, city_id: str) -> City | None:
        """Retrieve city metadata by unique identifier."""
        return self._cities.get(city_id)

    def list_options(
        self,
        city_id: str,
        category: ServiceCategory | None = None,
    ) -> Sequence[ServiceOption]:
        """List options for a city, optionally filtered by service category."""
        option_ids = self._city_options.get(city_id, [])
        options = [self._options[oid] for oid in option_ids]
        if category is not None:
            options = [opt for opt in options if opt.category == category]
        return tuple(options)

    def list_options_by_city_and_category(
        self,
        city_id: str,
        category: ServiceCategory,
    ) -> Sequence[ServiceOption]:
        """List options strictly matching the given city and category."""
        return self.list_options(city_id, category=category)

    def get_option(self, option_id: str) -> ServiceOption | None:
        """Retrieve a specific service option by its unique identifier."""
        return self._options.get(option_id)

    def is_verified(self, option_id: str) -> bool:
        """Return True if option has verified metadata (last_verified_at is not None)."""
        if option_id not in self._options:
            raise KeyError(f"Option not found: {option_id!r}")
        return option_id not in self._unverified_option_ids

    def get_freshness_status(
        self,
        option_id: str,
        reference_time: datetime | None = None,
    ) -> FreshnessStatus | None:
        """Return freshness classification for a verified option, or None if unverified."""
        if option_id not in self._options:
            raise KeyError(f"Option not found: {option_id!r}")
        if option_id in self._unverified_option_ids:
            return None
        option = self._options[option_id]
        ref = reference_time or datetime.now(UTC)
        return freshness_status(option.last_verified_at, ref)

    def list_unverified_options(
        self,
        city_id: str | None = None,
    ) -> Sequence[ServiceOption]:
        """Return options whose verification status is unverified (last_verified_at is None)."""
        if city_id is not None:
            option_ids = self._city_options.get(city_id, [])
            return tuple(
                self._options[oid] for oid in option_ids if oid in self._unverified_option_ids
            )
        return tuple(
            self._options[oid]
            for oid in self._unverified_option_ids
            if oid in self._options
        )
