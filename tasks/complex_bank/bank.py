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
        # BUG: negative deposits are accepted
        self._balance += amount
        self._transactions.append(Transaction("deposit", amount))

    def withdraw(self, amount: float) -> None:
        # BUG: overdraft_limit is not checked — always raises when balance < amount
        if amount > self._balance:
            raise InsufficientFundsError(f"Cannot withdraw {amount}, balance is {self._balance}")
        self._balance -= amount
        self._transactions.append(Transaction("withdrawal", amount))

    def transfer(self, amount: float, target: "BankAccount") -> None:
        # MISSING: not implemented
        pass

    def get_history(self) -> List[Transaction]:
        # BUG: returns a mutable reference — external code can alter internal state
        return self._transactions

    def net_flow(self) -> float:
        # BUG: wrong sign — subtracts deposits and adds withdrawals
        total = 0.0
        for t in self._transactions:
            if t.kind in ("deposit", "transfer_in"):
                total -= t.amount
            else:
                total += t.amount
        return total
