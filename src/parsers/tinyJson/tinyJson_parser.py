from parsers.common import *

type Json = str | int | dict[str, Json]

def ruleJson(toks: TokenStream) -> Json:
    """
    Parses a JSON object, a JSON string, or a JSON number.
    """
    if toks.lookahead().type == 'STRING':
        t=toks.next()
        return str(t.value)[1:-1]
    elif toks.lookahead().type == 'INT':
        t=toks.next()
        return int(t.value)
    else:
        t=toks.next()
        return ruleEntryList(toks)

def ruleEntryList(toks: TokenStream) -> dict[str, Json]:
    """
    Parses the content of a JSON object.
    """
    if toks.lookahead().type=='RBRACE':
        t=toks.next()
        return {}
    else:
        result={}
        while toks.lookahead().type!='RBRACE':
            if toks.lookahead().type!='COMMA':
                t=ruleEntry(toks)
                result[t[0]]=t[1]
            else:
                _=toks.next()
        _=toks.next()
        return result # type: ignore

def ruleEntry(toks: TokenStream) -> tuple[str, Json]:
    s=toks.ensureNext('STRING')[1:-1]
    _=toks.ensureNext('COLON')
    j=ruleJson(toks)

    return (s, j)

def parse(code: str) -> Json:
    parser = mkLexer("./src/parsers/tinyJson/tinyJson_grammar.lark")
    tokens = list(parser.lex(code))
    log.info(f'Tokens: {tokens}')
    toks = TokenStream(tokens)
    res = ruleJson(toks)
    toks.ensureEof(code)
    return res
