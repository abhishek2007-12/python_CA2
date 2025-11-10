import datetime as dt
import sys
from typing import Dict, Tuple

import requests
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox

API_BASE = "https://api.frankfurter.app"


# ---------- Core functions (Frankfurter-compatible) ----------

def fetch_conversion(amount: float, base: str, target: str) -> Tuple[float, float]:
    """
    Returns (converted_amount, rate) using t7he latest available rate via Frankfurter.
    Frankfurter latest endpoint:
      GET /latest?amount=...&from=...&to=...
    Response example:
      { "amount": 10.0, "base": "USD", "date": "2025-11-10", "rates": {"INR": 835.12} }
    """
    if base == target:
        return amount, 1.0

    url = f"{API_BASE}/latest"
    params = {"amount": amount, "from": base, "to": target}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    rates = data.get("rates", {})
    if target not in rates:
        raise ValueError(f"No rate returned for {base}->{target}. Response: {data}")

    converted = float(rates[target])
    # The unit rate is for 1 base, so ask again with amount=1 (or divide converted/amount)
    rate = converted / amount if amount != 0 else float("nan")
    return converted, rate


def fetch_timeseries(base: str, target: str, days: int = 30) -> Dict[str, float]:
    """
    Returns dict { 'YYYY-MM-DD': rate } for the past `days` calendar days via Frankfurter.
    Frankfurter timeseries style: /YYYY-MM-DD..YYYY-MM-DD?from=USD&to=INR
    """
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    url = f"{API_BASE}/{start.isoformat()}..{end.isoformat()}"
    params = {"from": base, "to": target}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    # data example:
    # { "amount": 1.0, "start_date": "...", "end_date": "...",
    #   "base": "USD", "rates": {"2025-10-20": {"INR": 83.2}, ... } }
    if "rates" not in data:
        raise ValueError(f"Timeseries failed: {data}")

    rates = {}
    for day in sorted(data["rates"].keys()):
        payload = data["rates"][day]
        val = payload.get(target)
        if val is not None:
            rates[day] = float(val)
    if not rates:
        raise ValueError("No historical rates returned.")
    return rates


# ---------- Plotting helpers ----------

def plot_rate_history(rates: Dict[str, float], base: str, target: str) -> None:
    dates = [dt.datetime.fromisoformat(d) for d in rates.keys()]
    values = list(rates.values())

    plt.figure()
    plt.plot(dates, values)
    plt.title(f"Exchange Rate: 1 {base} in {target} (Last {len(values)} Days)")
    plt.xlabel("Date")
    plt.ylabel(f"Rate ({target} per {base})")
    plt.grid(True)
    plt.tight_layout()


def plot_today_vs_avg(today_rate: float, avg_rate: float, base: str, target: str) -> None:
    labels = ["Today", "Period Avg"]
    values = [today_rate, avg_rate]

    plt.figure()
    plt.bar(labels, values)
    plt.title(f"Rate Difference: {base} → {target}")
    plt.ylabel(f"{target} per {base}")
    for i, v in enumerate(values):
        plt.text(i, v, f"{v:.4f}", ha="center", va="bottom")
    plt.tight_layout()


def plot_amount_comparison(original_amount: float, converted_amount: float, base: str, target: str) -> None:
    labels = [f"Original ({base})", f"Converted ({target})"]
    values = [original_amount, converted_amount]

    plt.figure()
    plt.bar(labels, values)
    plt.title(f"Amount Comparison: {base} → {target}")
    plt.ylabel("Amount")
    for i, v in enumerate(values):
        plt.text(i, v, f"{v:.4f}", ha="center", va="bottom")
    plt.tight_layout()


# ---------- Utilities ----------

def normalize_ccy(ccy: str) -> str:
    c = ccy.strip().upper()
    if len(c) != 3 or not c.isalpha():
        raise ValueError(f"Invalid currency code: {ccy!r}. Use ISO 4217 codes like USD, EUR, INR.")
    return c


# ---------- Tkinter GUI ----------

class CurrencyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Currency Converter (Frankfurter)")
        self.geometry("520x360")
        self.resizable(False, False)

        # Inputs
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        self.amount_var = tk.StringVar(value="100")
        self.base_var = tk.StringVar(value="INR")
        self.target_var = tk.StringVar(value="USD")
        self.days_var = tk.StringVar(value="30")

        ttk.Label(frm, text="Amount").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(frm, textvariable=self.amount_var, width=20).grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(frm, text="Base (e.g., USD, INR)").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(frm, textvariable=self.base_var, width=20).grid(row=1, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(frm, text="Target (e.g., USD, INR)").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(frm, textvariable=self.target_var, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(frm, text="History days").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(frm, textvariable=self.days_var, width=20).grid(row=3, column=1, sticky="w", padx=6, pady=6)

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="Convert & Plot", command=self.on_convert).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="Clear Output", command=self.clear_output).grid(row=0, column=1, padx=6)

        # Output box
        ttk.Label(frm, text="Output").grid(row=5, column=0, sticky="nw", padx=6, pady=6)
        self.output = tk.Text(frm, height=10, width=60, wrap="word")
        self.output.grid(row=5, column=1, sticky="w", padx=6, pady=6)

        for i in range(2):
            frm.columnconfigure(i, weight=1)

    def clear_output(self):
        self.output.delete("1.0", tk.END)

    def on_convert(self):
        try:
            amount = float(self.amount_var.get())
            base = normalize_ccy(self.base_var.get())
            target = normalize_ccy(self.target_var.get())
            days_str = self.days_var.get().strip()
            days = int(days_str) if days_str else 30
            if days < 1:
                raise ValueError("History days must be >= 1")

            converted, today_rate = fetch_conversion(amount, base, target)

            self.clear_output()
            self._write_line("-" * 50)
            self._write_line(f"Amount       : {amount:.4f} {base}")
            self._write_line(f"Current rate : 1 {base} = {today_rate:.6f} {target}")
            self._write_line(f"Converted    : {converted:.4f} {target}")
            self._write_line("-" * 50)

            # Historical charts
            rates = fetch_timeseries(base, target, days=days)

            # Average excluding (potential) last day if it's today
            dates_sorted = list(rates.keys())
            if dates_sorted:
                last_day = dates_sorted[-1]
                is_today_included = (last_day == dt.date.today().isoformat())
            else:
                is_today_included = False

            values = list(rates.values())
            if is_today_included and len(values) > 1:
                avg_rate = sum(values[:-1]) / (len(values) - 1)
            else:
                avg_rate = sum(values) / len(values)

            self._write_line(f"Avg rate ({days}d window): {avg_rate:.6f} {target}/{base}")
            self._write_line("Close the charts to continue...")

            # Make the plots in separate windows
            plot_rate_history(rates, base, target)
            plot_today_vs_avg(today_rate, avg_rate, base, target)
            plot_amount_comparison(amount, converted, base, target)
            plt.show()

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Network Error", f"Error while fetching rates.\n\nDetails:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _write_line(self, text: str):
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)


if __name__ == "__main__":
    try:
        app = CurrencyApp()
        app.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
