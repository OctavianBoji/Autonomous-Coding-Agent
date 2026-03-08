import pytest
from bank import BankAccount, InsufficientFundsError


# ── deposit ──────────────────────────────────────────────────────────────────

def test_deposit_increases_balance():
    acc = BankAccount("Alice")
    acc.deposit(100)
    assert acc.balance == 100

def test_deposit_negative_raises():
    acc = BankAccount("Alice")
    with pytest.raises(ValueError):
        acc.deposit(-50)

def test_deposit_zero_raises():
    acc = BankAccount("Alice")
    with pytest.raises(ValueError):
        acc.deposit(0)


# ── withdraw ─────────────────────────────────────────────────────────────────

def test_withdraw_reduces_balance():
    acc = BankAccount("Alice", balance=200)
    acc.withdraw(80)
    assert acc.balance == 120

def test_withdraw_insufficient_funds_raises():
    acc = BankAccount("Alice", balance=50)
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(100)

def test_withdraw_within_overdraft_limit():
    acc = BankAccount("Alice", balance=30, overdraft_limit=50)
    acc.withdraw(70)           # 30 + 50 overdraft covers this
    assert acc.balance == -40

def test_withdraw_beyond_overdraft_raises():
    acc = BankAccount("Alice", balance=10, overdraft_limit=20)
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(50)       # 10 + 20 = 30 available, need 50


# ── transfer ─────────────────────────────────────────────────────────────────

def test_transfer_moves_funds():
    alice = BankAccount("Alice", balance=500)
    bob = BankAccount("Bob", balance=100)
    alice.transfer(200, bob)
    assert alice.balance == 300
    assert bob.balance == 300

def test_transfer_insufficient_funds_raises():
    alice = BankAccount("Alice", balance=50)
    bob = BankAccount("Bob")
    with pytest.raises(InsufficientFundsError):
        alice.transfer(100, bob)

def test_transfer_records_both_sides():
    alice = BankAccount("Alice", balance=300)
    bob = BankAccount("Bob")
    alice.transfer(100, bob)
    assert any(t.kind == "transfer_out" for t in alice.get_history())
    assert any(t.kind == "transfer_in"  for t in bob.get_history())


# ── history ───────────────────────────────────────────────────────────────────

def test_get_history_returns_copy():
    acc = BankAccount("Alice", balance=100)
    acc.deposit(50)
    history = acc.get_history()
    history.clear()            # mutating the returned list must NOT affect account
    assert len(acc.get_history()) == 1

def test_history_records_all_operations():
    acc = BankAccount("Alice", balance=200)
    acc.deposit(50)
    acc.withdraw(30)
    kinds = [t.kind for t in acc.get_history()]
    assert kinds == ["deposit", "withdrawal"]


# ── net_flow ──────────────────────────────────────────────────────────────────

def test_net_flow_positive():
    acc = BankAccount("Alice")
    acc.deposit(100)
    acc.deposit(50)
    assert acc.net_flow() == 150

def test_net_flow_mixed():
    acc = BankAccount("Alice", balance=200)
    acc.deposit(100)
    acc.withdraw(60)
    assert acc.net_flow() == 40   # +100 - 60

def test_net_flow_with_transfer():
    alice = BankAccount("Alice", balance=500)
    bob = BankAccount("Bob")
    alice.transfer(200, bob)
    assert alice.net_flow() == -200
    assert bob.net_flow() == 200
