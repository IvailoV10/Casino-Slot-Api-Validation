from decimal import Decimal, InvalidOperation

VALID_SPIN_MODES = {"Normal", "FreeSpins", "WinSpins", "WildSpins", "Respin"}


class SlotValidator:
    """Core validation engine checking contract, types, formats, and calculations."""

    def __init__(self, fixture_name: str, data: dict):
        self.fixture_name = fixture_name
        self.data = data
        self.errors = []

    def validate(self) -> list:
        result = self._get_result()
        if not result:
            return [f"[{self.fixture_name}] Contract Error: 'response.body.result' is missing."]

        self._validate_contract_and_structure(result)
        self._validate_types_and_formats(result)
        self._validate_cross_field_consistency(result)
        return self.errors

    def _get_result(self) -> dict:
        try:
            return self.data["response"]["body"]["result"]
        except (KeyError, TypeError):
            return None

    def _to_decimal(self, value, field_path: str):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError):
            self.errors.append(
                f"[{self.fixture_name}] Type Error: Field '{field_path}' value '{value}' is not a valid decimal string.")
            return None

    def _validate_contract_and_structure(self, result: dict):
        # Rule 6.1: win and winsMultipliers requirements
        win = result.get("win")
        if not isinstance(win, dict):
            self.errors.append(f"[{self.fixture_name}] Contract Error: 'win' object is missing or invalid.")
        else:
            if "lines" not in win or "total" not in win:
                self.errors.append(
                    f"[{self.fixture_name}] Contract Error: 'win' must contain both 'lines' and 'total'. Found keys: {list(win.keys())}")

        wins_mult = result.get("winsMultipliers")
        if not isinstance(wins_mult, dict):
            self.errors.append(f"[{self.fixture_name}] Contract Error: 'winsMultipliers' object is missing or invalid.")
        else:
            if "lines" not in wins_mult or "total" not in wins_mult:
                self.errors.append(
                    f"[{self.fixture_name}] Contract Error: 'winsMultipliers' must contain both 'lines' and 'total'.")

        # Rule 6.2: winLines structure
        if "winLines" in result:
            win_lines = result["winLines"]
            if not isinstance(win_lines, list):
                self.errors.append(f"[{self.fixture_name}] Contract Error: 'winLines' must be an array.")
            else:
                required_fields = {"index", "start", "length", "tile", "multiplier", "amount", "multipliedAmount",
                                   "tiles"}
                for idx, entry in enumerate(win_lines):
                    missing = required_fields - entry.keys()
                    if missing:
                        self.errors.append(
                            f"[{self.fixture_name}] Contract Error: winLines[{idx}] missing fields: {missing}")

        # Rule 6.3: reelsBuffer width check for base mode
        reels_buffer = result.get("reelsBuffer")
        spin_mode = result.get("spinMode")
        if reels_buffer is not None:
            if not isinstance(reels_buffer, list):
                self.errors.append(f"[{self.fixture_name}] Contract Error: 'reelsBuffer' must be an array.")
            elif spin_mode == "Normal" and len(reels_buffer) != 5:
                self.errors.append(
                    f"[{self.fixture_name}] Contract Error: Base mode 'reelsBuffer' expected width of 5 reels, found {len(reels_buffer)}.")

        # Rule 6.4: Optional arrays check
        optional_arrays = ["cashSymbols", "collectors", "collectorsBuffer", "scatters", "features", "freeSpins",
                           "respin"]
        for arr_field in optional_arrays:
            if arr_field in result and not isinstance(result[arr_field], list):
                self.errors.append(f"[{self.fixture_name}] Contract Error: Field '{arr_field}' must be an array.")

    def _validate_types_and_formats(self, result: dict):
        # Rule 5.1: Monetary values decimal-safe with 2 fraction digits
        monetary_paths = [
            ("win", "lines"), ("win", "total"),
            ("winsMultipliers", "lines"), ("winsMultipliers", "total"),
            ("stake", None)
        ]

        for parent, field in monetary_paths:
            if parent in result:
                val = result[parent] if field is None else result[parent].get(field)
                path_str = f"{parent}.{field}" if field else parent
                if val is not None:
                    dec_val = self._to_decimal(val, path_str)
                    if dec_val is not None:
                        parts = str(dec_val).split('.')
                        if len(parts) == 2 and len(parts[1]) != 2:
                            self.errors.append(
                                f"[{self.fixture_name}] Format Error: '{path_str}' value '{val}' must have exactly two fraction digits.")

        # Rule 5.2: Numeric fields
        multiplier = result.get("multiplier")
        if multiplier is not None:
            if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool) or multiplier <= 0:
                self.errors.append(
                    f"[{self.fixture_name}] Type Error: 'multiplier' must be a numeric and positive value. Found: {multiplier}")

        game_mode = result.get("gameMode")
        if game_mode is not None and not isinstance(game_mode, (int, float)):
            self.errors.append(f"[{self.fixture_name}] Type Error: 'gameMode' must be numeric when present.")

        # Rule 5.3: Enumerations
        spin_mode = result.get("spinMode")
        if spin_mode not in VALID_SPIN_MODES:
            self.errors.append(
                f"[{self.fixture_name}] Enum Error: 'spinMode' value '{spin_mode}' is invalid. Allowed: {VALID_SPIN_MODES}")

    def _validate_cross_field_consistency(self, result: dict):
        stake_val = self._to_decimal(result.get("stake"), "stake")

        # Rule 7.4: Entry-level formulas for winLines
        if "winLines" in result and isinstance(result["winLines"], list):
            for idx, entry in enumerate(result["winLines"]):
                amt = self._to_decimal(entry.get("amount"), f"winLines[{idx}].amount")
                mult = self._to_decimal(entry.get("multiplier"), f"winLines[{idx}].multiplier")
                mult_amt = self._to_decimal(entry.get("multipliedAmount"), f"winLines[{idx}].multipliedAmount")

                if amt is not None and mult is not None and mult_amt is not None:
                    expected_mult_amt = amt * mult
                    if mult_amt != expected_mult_amt:
                        self.errors.append(
                            f"[{self.fixture_name}] Calculation Error: winLines[{idx}] multipliedAmount ({mult_amt}) does not equal amount ({amt}) * multiplier ({mult}).")

        # Check cashSymbols amount calculation if present
        for symbol_key in ["cashSymbols", "cashSymbolsBuffer"]:
            if symbol_key in result and isinstance(result[symbol_key], list) and stake_val:
                for idx, entry in enumerate(result[symbol_key]):
                    amt = self._to_decimal(entry.get("amount"), f"{symbol_key}[{idx}].amount")
                    mult = self._to_decimal(entry.get("multiplier"), f"{symbol_key}[{idx}].multiplier")
                    if amt is not None and mult is not None:
                        expected_amt = mult * stake_val
                        if amt != expected_amt:
                            self.errors.append(
                                f"[{self.fixture_name}] Calculation Error: {symbol_key}[{idx}] amount ({amt}) does not equal multiplier ({mult}) * stake ({stake_val}).")