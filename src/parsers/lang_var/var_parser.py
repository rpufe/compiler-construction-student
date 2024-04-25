from lark import ParseTree
from lang_var.var_ast import *
from parsers.common import *
import common.log as log

grammarFile = "./src/parsers/lang_var/var_grammar.lark"

def parse(args: ParserArgs) -> exp:
    parseTree = parseAsTree(args, grammarFile, 'lvar')
    ast = parseTreeToExpAst(parseTree)
    log.debug(f'AST: {ast}')
    return ast

def parseTreeToExpAst(t: ParseTree) -> exp:
    match t.data:
        case 'int_exp':
            return IntConst(int(asToken(t.children[0])))
        case 'add_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Add(), parseTreeToExpAst(e2))
        case 'mul_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Mul(), parseTreeToExpAst(e2))
        case 'exp_1' | 'exp_2' | 'paren_exp':
            return parseTreeToExpAst(asTree(t.children[0]))
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for exp: {t}')
        
def parseModule(args: ParserArgs) -> mod:
    parseTree = parseAsTree(args, grammarFile, 'lvar')
    ast = parseTreeToModuleAst(parseTree)
    log.debug(f'AST: {ast}')
    return ast

def parseTreeToModuleAst(t: ParseTree) -> mod:
    match t.data:
        case 
        
def parseTreeToStmtAst(t: ParseTree) -> stmt:
    return 0

def parseTreeToStmtListAst(t: ParseTree) -> list[stmt]:
    return 0
