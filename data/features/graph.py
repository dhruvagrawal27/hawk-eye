"""Graph feature family (DATA-21; blueprint Part 6.5 + Part 12 slow-lane signals).

Feeds the L5 graph layer. Every 6.5 feature plus slow-lane additions over a flattened
L0 DataFrame:

  * degree / centrality in the beneficiary/counterparty graph
  * shared device / IP / address / phone links between employees & beneficiaries
  * circular-flow / round-tripping / mule-chain motifs
  * maker-checker collusion subgraphs
  * employee <-> customer-account linkage
  * SLOW: vendor-address == employee-address
  * SLOW: single-client vendor
  * SLOW: round / sequential invoice numbering
  * SLOW: duplicated bank-details clusters (ghost-employee/payroll)

networkx is OPTIONAL: a pure numpy/pandas fallback computes degree and an
iterative (power-method) approximation of eigenvector centrality. Cycle detection
uses a pure-python DFS so it never needs networkx.

Status: REAL (numpy/pandas; networkx optional).
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

try:  # optional accelerator
    import networkx as nx  # type: ignore

    _HAVE_NX = True
except Exception:  # pragma: no cover - exercised only when nx absent
    nx = None  # type: ignore
    _HAVE_NX = False

E = "actor.employee_id"
VERB = "action.verb"
BENE = "object.beneficiary_id"
ACCT = "object.account_id"
MAKER = "linkage.maker_id"
CHECKER = "linkage.checker_id"
CUST = "linkage.customer_account"
DEVICE = "context.device"
IP = "context.src_ip"
# slow-lane attribute columns the simulator may stamp
VENDOR = "object.beneficiary_id"
EMP_ADDR = "actor.address"
VEN_ADDR = "object.address"
PHONE = "object.phone"
BANK_DETAILS = "object.bank_details"
INVOICE = "object.invoice_no"


def beneficiary_degree(df: pd.DataFrame) -> pd.Series:
    """Per-employee out-degree in the employee->beneficiary graph (distinct beneficiaries
    paid). A hub employee touching many beneficiaries is notable."""
    if df.empty or BENE not in df.columns:
        return pd.Series(dtype=int)
    d = df.dropna(subset=[BENE])
    return d.groupby(E)[BENE].nunique().rename("beneficiary_degree")


def _edges_employee_beneficiary(df: pd.DataFrame) -> list[tuple[str, str]]:
    d = df.dropna(subset=[BENE]) if BENE in df.columns else df.iloc[0:0]
    return [(f"E:{r[E]}", f"B:{r[BENE]}") for _, r in d.iterrows()]


def eigenvector_centrality(df: pd.DataFrame, iters: int = 100) -> pd.Series:
    """Eigenvector centrality on the bipartite employee/beneficiary graph.

    Uses networkx when available, else a pure power-iteration on the adjacency matrix.
    Returns centrality for employee nodes (index = employee_id).
    """
    edges = _edges_employee_beneficiary(df)
    if not edges:
        return pd.Series(dtype=float)
    if _HAVE_NX:
        g = nx.Graph()
        g.add_edges_from(edges)
        try:
            cent = nx.eigenvector_centrality(g, max_iter=500, tol=1e-04)
        except Exception:
            cent = nx.degree_centrality(g)
        return pd.Series({n[2:]: v for n, v in cent.items() if n.startswith("E:")},
                         name="eigenvector_centrality")
    # pure-python power iteration
    nodes = sorted({n for e in edges for n in e})
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    adj = np.zeros((n, n))
    for a, b in edges:
        adj[idx[a], idx[b]] = 1
        adj[idx[b], idx[a]] = 1
    x = np.ones(n) / np.sqrt(n)
    for _ in range(iters):
        x_new = adj @ x
        norm = np.linalg.norm(x_new)
        if norm < 1e-12:
            break
        x = x_new / norm
    return pd.Series({nodes[i][2:]: float(x[i]) for i in range(n) if nodes[i].startswith("E:")},
                     name="eigenvector_centrality")


def shared_attribute_links(df: pd.DataFrame, attr: str = DEVICE) -> pd.DataFrame:
    """Pairs of employees sharing an attribute (device / IP / address / phone). Returns a
    DataFrame of (attr_value, employees) where >1 employee shares the value."""
    if df.empty or attr not in df.columns:
        return pd.DataFrame(columns=["attr", "value", "employees", "n"])
    d = df.dropna(subset=[attr])
    grp = d.groupby(attr)[E].apply(lambda s: sorted(set(map(str, s))))
    rows = [{"attr": attr, "value": v, "employees": emps, "n": len(emps)}
            for v, emps in grp.items() if len(emps) > 1]
    return pd.DataFrame(rows, columns=["attr", "value", "employees", "n"])


def circular_flow_motifs(df: pd.DataFrame, max_len: int = 6) -> list[list[str]]:
    """Detect cycles (round-tripping / mule chains) in the account->account transfer
    graph built from object.account_id -> linkage.customer_account on transfer verbs.

    Pure-python DFS cycle enumeration (bounded length). Returns list of node cycles.
    """
    if df.empty or ACCT not in df.columns or CUST not in df.columns:
        return []
    d = df[df[VERB].isin(["transfer", "post_payment", "approve_payment"])].dropna(subset=[ACCT, CUST])
    adj: dict[str, set[str]] = defaultdict(set)
    for _, r in d.iterrows():
        adj[str(r[ACCT])].add(str(r[CUST]))
    cycles: list[list[str]] = []
    seen_keys: set[frozenset] = set()

    def dfs(start: str, node: str, path: list[str]) -> None:
        if len(path) > max_len:
            return
        for nxt in adj.get(node, ()):
            if nxt == start and len(path) >= 2:
                key = frozenset(path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    cycles.append(path + [start])
            elif nxt not in path:
                dfs(start, nxt, path + [nxt])

    for s in list(adj.keys()):
        dfs(s, s, [s])
    return cycles


def maker_checker_collusion(df: pd.DataFrame, min_pairs: int = 3) -> pd.DataFrame:
    """Maker-checker pairs that co-occur far more than expected (collusion subgraph).
    Returns pairs with count >= min_pairs."""
    if df.empty or MAKER not in df.columns or CHECKER not in df.columns:
        return pd.DataFrame(columns=["maker", "checker", "count"])
    d = df.dropna(subset=[MAKER, CHECKER])
    if d.empty:
        return pd.DataFrame(columns=["maker", "checker", "count"])
    counts = d.groupby([MAKER, CHECKER]).size().reset_index(name="count")
    counts = counts.rename(columns={MAKER: "maker", CHECKER: "checker"})
    return counts[counts["count"] >= min_pairs].reset_index(drop=True)


def employee_customer_linkage(df: pd.DataFrame) -> pd.DataFrame:
    """Direct employee <-> customer-account links (an employee transacting on an account
    that resolves to their own identity is a conflict). Returns (employee, customer_account)."""
    if df.empty or CUST not in df.columns:
        return pd.DataFrame(columns=["employee", "customer_account", "self_link"])
    d = df.dropna(subset=[CUST])
    out = d.groupby([E, CUST]).size().reset_index(name="n")
    out = out.rename(columns={E: "employee", CUST: "customer_account"})
    out["self_link"] = out.apply(
        lambda r: str(r["employee"]) in str(r["customer_account"]), axis=1)
    return out


# ---- slow-lane signals -------------------------------------------------------
def vendor_address_eq_employee(df: pd.DataFrame) -> pd.DataFrame:
    """SLOW (fake-vendor/billing): vendor address == an employee address. Returns the
    matching (employee, vendor, address) rows."""
    if df.empty or EMP_ADDR not in df.columns or VEN_ADDR not in df.columns:
        return pd.DataFrame(columns=["employee", "vendor", "address"])
    emp_addr = df.dropna(subset=[EMP_ADDR]).groupby(E)[EMP_ADDR].first()
    ven = df.dropna(subset=[VEN_ADDR, VENDOR])[[VENDOR, VEN_ADDR]].drop_duplicates()
    rows = []
    addr_to_emp: dict[str, list[str]] = defaultdict(list)
    for emp, addr in emp_addr.items():
        addr_to_emp[str(addr)].append(str(emp))
    for _, r in ven.iterrows():
        for emp in addr_to_emp.get(str(r[VEN_ADDR]), []):
            rows.append({"employee": emp, "vendor": str(r[VENDOR]), "address": str(r[VEN_ADDR])})
    return pd.DataFrame(rows, columns=["employee", "vendor", "address"])


def single_client_vendor(df: pd.DataFrame) -> pd.Series:
    """SLOW: vendors paid by exactly ONE employee/client (a captive shell vendor).
    Returns per-vendor count of distinct payers; flag where == 1."""
    if df.empty or VENDOR not in df.columns:
        return pd.Series(dtype=bool)
    d = df[df[VERB].isin(["pay_invoice", "approve_invoice", "post_payment"])].dropna(subset=[VENDOR])
    if d.empty:
        return pd.Series(dtype=bool)
    payers = d.groupby(VENDOR)[E].nunique()
    return (payers == 1).rename("single_client_vendor")


def sequential_invoice_numbering(df: pd.DataFrame) -> pd.Series:
    """SLOW: per-vendor flag when invoice numbers are perfectly/near sequential (a sign
    that the vendor bills only this client). Reads object.invoice_no."""
    if df.empty or INVOICE not in df.columns or VENDOR not in df.columns:
        return pd.Series(dtype=bool)
    out = {}
    d = df.dropna(subset=[INVOICE, VENDOR])
    for ven, grp in d.groupby(VENDOR):
        nums = pd.to_numeric(grp[INVOICE], errors="coerce").dropna().sort_values().values
        if len(nums) < 3:
            out[str(ven)] = False
            continue
        diffs = np.diff(nums)
        out[str(ven)] = bool(np.all(diffs == 1) or (np.mean(diffs == 1) > 0.6))
    return pd.Series(out, name="sequential_invoice_numbering")


def duplicated_bank_details(df: pd.DataFrame) -> pd.DataFrame:
    """SLOW (ghost-employee/payroll): bank-detail values shared across multiple payees.
    Returns (bank_details, payees, n) for clusters of size > 1."""
    if df.empty or BANK_DETAILS not in df.columns:
        return pd.DataFrame(columns=["bank_details", "payees", "n"])
    key = CUST if CUST in df.columns else E
    d = df.dropna(subset=[BANK_DETAILS])
    grp = d.groupby(BANK_DETAILS)[key].apply(lambda s: sorted(set(map(str, s))))
    rows = [{"bank_details": str(v), "payees": p, "n": len(p)} for v, p in grp.items() if len(p) > 1]
    return pd.DataFrame(rows, columns=["bank_details", "payees", "n"])


def demo_frame() -> pd.DataFrame:
    """Frame with a collusion pair, a circular flow, a fake vendor, and shared bank details."""
    rows = []
    # collusion maker-checker pair (>=3)
    for i in range(4):
        rows.append({E: "EMP-maker", VERB: "approve_payment", MAKER: "EMP-maker",
                     CHECKER: "EMP-checker", BENE: f"BEN-{i}", ACCT: "ACCT-1", CUST: "ACCT-2",
                     DEVICE: "WS-1"})
    # circular flow ACCT-2 -> ACCT-3 -> ACCT-2
    rows.append({E: "EMP-x", VERB: "transfer", ACCT: "ACCT-2", CUST: "ACCT-3"})
    rows.append({E: "EMP-x", VERB: "transfer", ACCT: "ACCT-3", CUST: "ACCT-2"})
    # fake vendor: vendor address == employee address; single client; sequential invoices
    for i in range(3):
        rows.append({E: "EMP-buyer", VERB: "pay_invoice", VENDOR: "BEN-vendor",
                     VEN_ADDR: "12 Main St", EMP_ADDR: None, INVOICE: 1000 + i})
    rows.append({E: "EMP-buyer", VERB: "login", EMP_ADDR: "12 Main St", VEN_ADDR: None})
    # duplicated bank details across two payees
    rows.append({E: "EMP-hr", VERB: "payroll_credit", CUST: "EMP-g1", BANK_DETAILS: "AC-999"})
    rows.append({E: "EMP-hr", VERB: "payroll_credit", CUST: "EMP-g2", BANK_DETAILS: "AC-999"})
    return pd.DataFrame(rows)
