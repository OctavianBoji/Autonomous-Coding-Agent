"""
BankAccount module.

TODO: Fix the bugs and implement the missing features so all tests pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class Transaction:
    kind: str          # "deposit" | "withdrawal" | "transfer_in" | "transfer_out"
    amount: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class InsufficientFundsError(Exception):
    pass

class BankAccount:
    def __init__(self, owner: str, balance: float = 0.0, overdraft_limit: float = 0.0):
        self.owner = owner
        self._balance = balance
        self._overdraft_limit = overdraft_limit
        self._transactions: List[Transaction] = []

    @property
    def balance(self) -> float:
        return self._balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive and greater than zero.")
        self._balance += amount
        self._transactions.append(Transaction("deposit", amount))

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive and greater than zero.")
        if amount > self._balance + self._overdraft_limit:
            raise InsufficientFundsError(f"Cannot withdraw {amount}, balance is {self._balance}, overdraft limit is {self._overdraft_limit}.")
        self._balance -= amount
        self._transactions.append(Transaction("withdrawal", amount))

    def transfer(self, amount: float, target: "BankAccount") -> None:
        if amount <= 0:
            raise ValueError("Transfer amount must be positive and greater than zero.")
        if amount > self._balance + self._overdraft_limit:
            raise InsufficientFundsError(f"Cannot transfer {amount}, balance is {self._balance}, overdraft limit is {self._overdraft_limit}.")
        self._balance -= amount
        target._balance += amount
        self._transactions.append(Transaction("transfer_out", amount))
        target._transactions.append(Transaction("transfer_in", amount))

    def get_history(self) -> List[Transaction]:
        return self._transactions.copy()

    def net_flow(self) -> float:
        total = 0.0
        for t in self._transactions:
            if t.kind in ("deposit", "transfer_in"):
                total += t.amount
            else:
                total -= t.amount
        return total
