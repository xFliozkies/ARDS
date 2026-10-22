"""Independent reviewed solution and exhaustive oracle: The Mirror Seal."""
import random


def candidate(data):
    # KMP prefix function of s + separator + reversed(s).
    s = data["s"]
    t = s + "#" + s[::-1]
    pi = [0] * len(t)
    for i in range(1, len(t)):
        j = pi[i - 1]
        while j and t[i] != t[j]:
            j = pi[j - 1]
        if t[i] == t[j]:
            j += 1
        pi[i] = j
    return pi[-1]


def oracle(data):
    # Literal specification: inspect every prefix for palindromic equality.
    s = data["s"]
    best = 0
    for n in range(1, len(s) + 1):
        p = s[:n]
        if p == p[::-1]:
            best = n
    return best


def edge_cases():
    return [
        {"s": "a"}, {"s": "b"}, {"s": "ab"}, {"s": "aa"},
        {"s": "aba"}, {"s": "abba"}, {"s": "abcabc"},
        {"s": "abbac"}, {"s": "a" * 2000},
        {"s": "ab" * 1000}, {"s": "a" * 1999 + "b"},
        {"s": "a" * 998 + "b" + "a" * 998 + "c"},
        {"s": "abc" * 666 + "ab"}
    ]


def generate_cases(seed, count):
    rng = random.Random(seed)
    cases = []
    for i in range(count):
        n = rng.randint(1, 100 if i % 7 else 300)
        if i % 9 == 0:
            word = "".join(rng.choice("abc") for _ in range((n + 1)//2))
            word = word + (word[::-1] if n % 2 == 0 else word[:-1][::-1])
        elif i % 11 == 0:
            word = rng.choice("abc") * n
        elif i % 13 == 0:
            word = ("abc" * (n // 3 + 1))[:n]
        else:
            word = "".join(rng.choice("abc") for _ in range(n))
        cases.append({"s": word})
    return cases



def decode_stdin(raw):
    tokens = raw.split()
    if len(tokens) != 1:
        raise ValueError("Expected exactly one string token from stdin")
    s = tokens[0]
    if not 1 <= len(s) <= 2000 or set(s) - set("abc"):
        raise ValueError("Input exceeds the reviewed input domain")
    return {"s": s}


def encode_stdout(value):
    if type(value) is not int or not 1 <= value <= 2000:
        raise ValueError("The reference output must be a valid length")
    return str(value) + chr(10)
