from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional, Tuple

import re

# === AST Node Definitions ===

class ExprNode:
    def eval(self, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("Must implement eval in subclass")


class LiteralNode(ExprNode):
    def __init__(self, value: str):
        # value is either an int, float, str, or re.Pattern
        self.value = value

    def eval(self, context: Dict[str, Any]) -> Any:
        # Literal simply returns its stored value
        return self.value


class VarNode(ExprNode):
    def __init__(self, name: str):
        self.name = name

    def eval(self, context: Dict[str, Any]) -> Any:
        # Look up the variable in context
        return context.get(self.name, '0')


class IndexNode(ExprNode):
    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index

    def eval(self, context: Dict[str, Any]) -> Any:
        val = context.get(self.name, '0')
        val = val.split(',')
        if self.index > len(val) -1: return '0'
        return val[self.index]


class UnaryOpNode(ExprNode):
    def __init__(self, op: str, child: ExprNode):
        self.op = op
        self.child = child

    def eval(self, context: Dict[str, Any]) -> Any:
        cval = self.child.eval(context)
        if self.op == "!":
            return not float(cval)
        raise RuntimeError(f"Unknown unary operator {self.op}")


class BinaryOpNode(ExprNode):
    def __init__(self, left: ExprNode, op: str, right: ExprNode):
        self.left = left
        self.op = op
        self.right = right

    def eval(self, context: Dict[str, Any]) -> Any:
        if self.op in ["and", "&&"]:
            if not self.left.eval(context): return False
            return self.right.eval(context)

        if self.op == "or":
            if self.left.eval(context): return True
            return self.right.eval(context)

        # For everything else, we evaluate both sides
        lv = self.left.eval(context)
        rv = self.right.eval(context)

        if self.op == "==": return str(lv) == str(rv)
        if self.op == "!=": return str(lv) != str(rv)
        if self.op == "<": return float(lv) < float(rv)
        if self.op == ">": return float(lv) > float(rv)
        if self.op == "<=": return float(lv) <= float(rv)
        if self.op == ">=": return float(lv) >= float(rv)

        if self.op == "=~":
            if not isinstance(rv, re.Pattern):
                raise TypeError("Right operand of =~ must be a regex pattern")
            return rv.search(str(lv)) is not None

        if self.op == "!~":
            if not isinstance(rv, re.Pattern):
                raise TypeError("Right operand of !~ must be a regex pattern")
            return rv.search(str(lv)) is None

        raise RuntimeError(f"Unknown binary operator {self.op}")

# === Parser & Tokenizer ===

Token = Tuple[str, str]
# Token types: 
#   "IDENT"  → alphanumeric identifier or keyword 
#   "NUMBER" → integer or float 
#   "STRING" → quoted string (like "COREONE") 
#   "REGEX"  → anything between /.../ 
#   "OP"     → one of ==, !=, >=, <=, >, <, =~, !~, !, and, or 
#   "LPAREN","RPAREN","LBRACK","RBRACK"

class Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens: List[Token] = self._tokenize(text)
        self.i = 0  # index into tokens

    def _tokenize(self, text: str) -> List[Token]:
        tokens: List[Token] = []
        i = 0
        length = len(text)

        while i < length:
            c = text[i]

            # Skip whitespace
            if c.isspace():
                i += 1
                continue

            # Parentheses / Brackets
            if c == "(":
                tokens.append(("LPAREN", c)); i += 1; continue
            if c == ")":
                tokens.append(("RPAREN", c)); i += 1; continue
            if c == "[":
                tokens.append(("LBRACK", c)); i += 1; continue
            if c == "]":
                tokens.append(("RBRACK", c)); i += 1; continue

            # Multi‐char operators: check longest first
            # Order matters: check 3‐character operators? We only have 2‐char: ==, !=, >=, <=, =~, !~, and the single‐char '!'
            if text.startswith("==", i):
                tokens.append(("OP", "==")); i += 2; continue
            if text.startswith("!=", i):
                tokens.append(("OP", "!=")); i += 2; continue
            if text.startswith(">=", i):
                tokens.append(("OP", ">=")); i += 2; continue
            if text.startswith("<=", i):
                tokens.append(("OP", "<=")); i += 2; continue
            if text.startswith("=~", i):
                tokens.append(("OP", "=~")); i += 2; continue
            if text.startswith("!~", i):
                tokens.append(("OP", "!~")); i += 2; continue
            if text.startswith("&&", i):
                tokens.append(("OP", "and")); i += 2; continue
            if text.startswith("||", i):
                tokens.append(("OP", "or")); i += 2; continue

            # Single‐char '>' or '<'
            if c == ">":
                tokens.append(("OP", ">")); i += 1; continue
            if c == "<":
                tokens.append(("OP", "<")); i += 1; continue

            # Single‐char '!'
            if c == "!":
                tokens.append(("OP", "!")); i += 1; continue

            # Regex literal: starts with '/'
            if c == "/":
                # Read until the next unescaped '/'
                j = i + 1
                while j < length:
                    if text[j] == "/" and text[j-1] != "\\":
                        break
                    j += 1
                if j >= length:
                    raise SyntaxError("Unterminated regex literal")
                pattern_body = text[i+1 : j]
                tokens.append(("REGEX", pattern_body))
                i = j + 1
                continue

            # Quoted string literal: " … " or ' … '
            if c in ("'", '"'):
                quote_char = c
                j = i + 1
                while j < length:
                    if text[j] == quote_char and text[j-1] != "\\":
                        break
                    j += 1
                if j >= length:
                    raise SyntaxError("Unterminated string literal")
                str_body = text[i+1 : j]
                # We do not interpret escape sequences here; we store raw content
                tokens.append(("STRING", str_body))
                i = j + 1
                continue

            # Number: [0-9]+(\.[0-9]+)?
            if c.isdigit():
                j = i
                while j < length and (text[j].isdigit() or text[j] == "."):
                    j += 1
                num_text = text[i:j]
                tokens.append(("NUMBER", num_text))
                i = j
                continue

            # Identifier or keyword (and/or)
            if c.isalpha() or c == "_":
                j = i
                while j < length and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                ident = text[i:j]
                if ident == "and":
                    tokens.append(("OP", "and"))
                elif ident == "or":
                    tokens.append(("OP", "or"))
                else:
                    tokens.append(("IDENT", ident))
                i = j
                continue

            # If we get here, it's an unexpected character
            raise SyntaxError(f"Unexpected character: {c}")

        return tokens

    def _peek(self) -> Optional[Token]:
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        return None

    def _advance(self) -> Token:
        if self.i >= len(self.tokens):
            raise SyntaxError("Unexpected end of input")
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _expect(self, ttype: str, value: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok is None:
            raise SyntaxError(f"Expected {ttype} but found end of input")
        if tok[0] != ttype or (value is not None and tok[1] != value):
            raise SyntaxError(f"Expected {ttype} {value!r} but found {tok}")
        return self._advance()

    def parse(self) -> ExprNode:
        node = self._parse_or()
        if self._peek() is not None:
            raise SyntaxError(f"Unexpected token after end: {self._peek()}")
        return node

    def _parse_or(self) -> ExprNode:
        left = self._parse_and()
        while True:
            tok = self._peek()
            if tok is not None and tok[0] == "OP" and tok[1] == "or":
                self._advance()
                right = self._parse_and()
                left = BinaryOpNode(left, "or", right)
            else:
                break
        return left

    def _parse_and(self) -> ExprNode:
        left = self._parse_not()
        while True:
            tok = self._peek()
            if tok is not None and tok[0] == "OP" and tok[1] == "and":
                self._advance()
                right = self._parse_not()
                left = BinaryOpNode(left, "and", right)
            else:
                break
        return left

    def _parse_not(self) -> ExprNode:
        tok = self._peek()
        # If we see a lone '!' (not followed by '=' or '~'), it is unary NOT
        if tok is not None and tok[0] == "OP" and tok[1] == "!":
            # Make sure it's not part of '!=' or '!~' (those would have been tokenized as OP("!=") or OP("!~"))
            self._advance()
            child = self._parse_not()
            return UnaryOpNode("!", child)
        else:
            return self._parse_comp()

    def _parse_comp(self) -> ExprNode:
        left = self._parse_atom()
        tok = self._peek()
        if tok is not None and tok[0] == "OP" and tok[1] in ("==", "!=", "<", ">", "<=", ">=", "=~", "!~"):
            op = tok[1]
            self._advance()
            right = self._parse_atom()
            return BinaryOpNode(left, op, right)
        return left

    def _parse_atom(self) -> ExprNode:
        tok = self._peek()
        if tok is None:
            raise SyntaxError("Unexpected end of input in atom")

        ttype, val = tok

        if ttype in ["STRING", "NUMBER"]:
            self._advance()
            return LiteralNode(val)

        if ttype == "REGEX":
            self._advance()

            try:
                pat = re.compile(val)
            except re.error as e:
                raise SyntaxError(f"Invalid regex /{val}/: {e}")
            
            return LiteralNode(pat)

        if ttype == "IDENT":
            # Could be a variable or keyword—but "and"/"or" handled earlier
            name = val
            self._advance()
            # Check for indexing: IDENT '[' NUMBER ']'
            nxt = self._peek()
            if nxt is not None and nxt[0] == "LBRACK":
                self._advance()  # consume '['
                idx_tok = self._expect("NUMBER")
                idx = int(idx_tok[1])
                self._expect("RBRACK")
                return IndexNode(name, idx)
            else:
                return VarNode(name)

        if ttype == "LPAREN":
            self._advance()
            node = self._parse_or()
            self._expect("RPAREN")
            return node

        raise SyntaxError(f"Unexpected token in atom: {tok}")