from typing import Dict, List, Set
import ast

def all_simple_paths_from_node(adj: Dict[str, List[str]], start: str) -> List[List[str]]:
    paths: List[List[str]] = []

    def visit(path: List[str], seen: Set[str]):
        cur = path[-1]

        for nb in adj.get(cur, []):
            if nb == start:
                paths.append(path + [nb])
                continue

            if nb in seen:
                continue

            seen.add(nb)
            path.append(nb)
            visit(path, seen)
            path.pop()
            seen.remove(nb)

        if len(path) > 1:
            paths.append(path.copy())

    visit([start], {start})
    return paths


def all_simple_paths(adj: Dict[str, List[str]]) -> List[List[str]]:
    collected: List[List[str]] = []

    for node in adj.keys():
        collected.extend(all_simple_paths_from_node(adj, node))

    for node in adj.keys():
        collected.append([node])

    unique: List[List[str]] = []
    seen = set()
    for p in collected:
        key = tuple(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    unique.sort(key=lambda x: -len(x))
    return unique


def is_subpath(small: List[str], big: List[str]) -> bool:
    if not small or len(small) > len(big):
        return False

    if small == big:
        return True

    length = len(small)
    for i in range(len(big) - length + 1):
        if big[i:i + length] == small:
            return True

    return False


def prime_paths_from_adj(adj: Dict[str, List[str]]) -> List[List[str]]:
    simple = all_simple_paths(adj)
    if not simple:
        return []

    primes: List[List[str]] = []

    for i, cur in enumerate(simple):
        prime = True
        for j, other in enumerate(simple):
            if i == j:
                continue
            if len(other) >= len(cur) and is_subpath(cur, other):
                prime = False
                break

        if prime and len(cur) >= 2:
            primes.append(cur)

    primes.sort(key=lambda x: (len(x), x))
    return primes



def cfg_from_code(source: str) -> Dict[str, List[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"خطای نحوی: {e}")
        return {}

    func_node = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            func_node = n
            break
    if not func_node:
        func_node = tree

    node_info = {}
    succ = {}
    idx = 0

    def new_node(kind: str, stmt: str = "") -> str:
        nonlocal idx
        nid = f"N{idx}"
        node_info[nid] = {"kind": kind, "code": stmt}
        succ[nid] = []
        idx += 1
        return nid

    entry = new_node("Entry")
    exit_n = new_node("Exit")
    cur_node = entry

    def handle_stmt(node: ast.AST) -> str:
        nonlocal cur_node

        if isinstance(node, ast.Assign):
            s = ast.unparse(node)
            n = new_node("Assign", s)
            succ[cur_node].append(n)
            cur_node = n
            return n

        if isinstance(node, ast.Expr):
            s = ast.unparse(node)
            n = new_node("Expr", s)
            succ[cur_node].append(n)
            cur_node = n
            return n

        if isinstance(node, ast.Return):
            s = ast.unparse(node)
            n = new_node("Return", s)
            succ[cur_node].append(n)
            succ[n].append(exit_n)
            cur_node = exit_n
            return n

        if isinstance(node, ast.If):
            test_s = ast.unparse(node.test)
            if_n = new_node("If", test_s)
            succ[cur_node].append(if_n)

            old = cur_node
            cur_node = if_n

            true_ends = []
            if node.body:
                for st in node.body:
                    handle_stmt(st)
                    true_ends.append(cur_node)
            true_exit = cur_node

            cur_node = if_n
            false_ends = []
            if node.orelse:
                for st in node.orelse:
                    handle_stmt(st)
                    false_ends.append(cur_node)
            false_exit = cur_node if false_ends else if_n

            merge = new_node("Merge")

            if true_ends:
                for e in true_ends:
                    if e != merge:
                        succ[e].append(merge)
            else:
                succ[if_n].append(merge)

            if false_ends:
                for e in false_ends:
                    if e != merge:
                        succ[e].append(merge)
            else:
                succ[if_n].append(merge)

            cur_node = merge
            return if_n

        if isinstance(node, ast.For):
            target_s = ast.unparse(node.target)
            iter_s = ast.unparse(node.iter)
            loop_n = new_node(f"For: {target_s} in {iter_s}")
            succ[cur_node].append(loop_n)

            cur_node = loop_n
            body_ends = []
            if node.body:
                for st in node.body:
                    handle_stmt(st)
                    body_ends.append(cur_node)

            if body_ends:
                for e in body_ends:
                    if e != loop_n:
                        succ[e].append(loop_n)

            exit_loop = new_node("For_Exit")
            succ[loop_n].append(exit_loop)
            cur_node = exit_loop
            return loop_n

        if isinstance(node, ast.While):
            test_s = ast.unparse(node.test)
            w_n = new_node("While", test_s)
            succ[cur_node].append(w_n)

            cur_node = w_n
            body_ends = []
            if node.body:
                for st in node.body:
                    handle_stmt(st)
                    body_ends.append(cur_node)

            if body_ends:
                for e in body_ends:
                    if e != w_n:
                        succ[e].append(w_n)

            exit_w = new_node("While_Exit")
            succ[w_n].append(exit_w)
            cur_node = exit_w
            return w_n

        stmt_s = ast.unparse(node) if hasattr(node, 'lineno') else str(node)
        n = new_node(node.__class__.__name__, stmt_s)
        succ[cur_node].append(n)
        cur_node = n
        return n

    body = func_node.body if hasattr(func_node, 'body') else func_node.body
    for st in body:
        handle_stmt(st)

    if cur_node != exit_n:
        if cur_node not in succ:
            succ[cur_node] = []
        if exit_n not in succ.get(cur_node, []):
            succ[cur_node].append(exit_n)

    adj_list: Dict[str, List[str]] = {}
    for nid in node_info:
        adj_list[nid] = succ.get(nid, [])

    if entry not in adj_list:
        adj_list[entry] = []
    if exit_n not in adj_list:
        adj_list[exit_n] = []

    return adj_list


def print_adjacency_list(adj: Dict[str, List[str]]):
    print("\nگراف CFG:")
    print("-" * 40)
    for node, neigh in sorted(adj.items()):
        print(f"{node:10} -> {neigh}")
    print("-" * 40)


if __name__ == '__main__':
    print("=" * 60)
    print("تست 1: گراف ساده")
    print("=" * 60)

    G = {
        'A': ['B', 'C'],
        'B': ['C', 'D'],
        'C': ['D'],
        'D': []
    }

    print("\nگراف:")
    for n, ns in G.items():
        print(f"{n} -> {ns}")

    print("\nPrime Paths:")
    for i, p in enumerate(prime_paths_from_adj(G), 1):
        print(f"{i:2d}. {p}")

    print("\n" + "=" * 60)
    print("تست 2: گراف با چرخه")
    print("=" * 60)

    G2 = {
        'A': ['B'],
        'B': ['C'],
        'C': ['A', 'D'],
        'D': []
    }

    print("\nگراف با چرخه:")
    for n, ns in G2.items():
        print(f"{n} -> {ns}")

    print("\nPrime Paths:")
    for i, p in enumerate(prime_paths_from_adj(G2), 1):
        print(f"{i:2d}. {p}")

    print("\n" + "=" * 60)
    print("تست 3: استخراج CFG از نمونه کد")
    print("=" * 60)

    src = '''
def f(x):
    if x > 0:
        y = 1
    else:
        y = -1
    for i in range(3):
        y += i
    return y
'''

    print("\nکد نمونه:")
    print(src)

    cfg = cfg_from_code(src)
    if cfg:
        print_adjacency_list(cfg)
        print("\nPrime Paths برای CFG:")
        cfg_primes = prime_paths_from_adj(cfg)
        if cfg_primes:
            for i, p in enumerate(cfg_primes, 1):
                print(f"{i:2d}. {p}")
        else:
            print("هیچ Prime Path یافت نشد!")
    else:
        print("خطا در استخراج CFG!")

    print("\n" + "=" * 60)
    print("تست 4: مثال پیچیده‌تر")
    print("=" * 60)

    src2 = '''
def find_max(a, b, c):
    max_val = a
    if b > max_val:
        max_val = b
    if c > max_val:
        max_val = c
    return max_val
'''

    print("\nکد نمونه 2:")
    print(src2)

    cfg2 = cfg_from_code(src2)
    if cfg2:
        print_adjacency_list(cfg2)
        print("\nPrime Paths:")
        cfg2_primes = prime_paths_from_adj(cfg2)
        if cfg2_primes:
            for i, p in enumerate(cfg2_primes, 1):
                print(f"{i:2d}. {p}")
        else:
            print("هیچ Prime Path یافت نشد!")
    else:
        print("خطا در استخراج CFG!")
