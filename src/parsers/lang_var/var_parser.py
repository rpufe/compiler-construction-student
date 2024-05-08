from lark import ParseTree
from lang_var.var_ast import *
from parsers.common import *
import common.log as log

grammarFile = "./src/parsers/lang_var/var_grammar.lark"

def parse(args: ParserArgs) -> exp:
    parseTree = parseAsTree(args, grammarFile, 'lvar') # type: ignore
    ast = parseTreeToExpAst(parseTree) # type: ignore
    log.debug(f'AST: {ast}')
    return ast

def parseTreeToExpAst(t: ParseTree) -> exp: # type: ignore
    match t.data: # type: ignore
        case 'int_exp':
            return IntConst(int(asToken(t.children[0]))) # type: ignore
        case 'add_exp':
            e1, e2 = [asTree(c) for c in t.children] # type: ignore
            return BinOp(parseTreeToExpAst(e1), Add(), parseTreeToExpAst(e2)) # type: ignore
        case 'mul_exp':
            e1, e2 = [asTree(c) for c in t.children] # type: ignore
            return BinOp(parseTreeToExpAst(e1), Mul(), parseTreeToExpAst(e2)) # type: ignore
        case 'exp_1' | 'exp_2' | 'paren_exp':
            return parseTreeToExpAst(t.children[0]) # type: ignore
        case 'neg_exp':
            return UnOp(USub(), parseTreeToExpAst(asTree(t.children[0]))) # type: ignore
        case 'sub_exp':
            e1, e2 = [asTree(c) for c in t.children] # type: ignore
            return BinOp(parseTreeToExpAst(e1), Sub(), parseTreeToExpAst(e2)) # type: ignore
        case 'function_call':
            name = Ident(asToken(t.children[0]).value) # type: ignore
            args = []
            for arg in t.children[1:]: # type: ignore
                if isinstance(arg, Token):
                    args+=[parseTreeToExpAst(arg)] # type: ignore
                else:
                    args+=[parseTreeToExpAst(asTree(arg))] # type: ignore
            return Call(name, args) # type: ignore
        case 'var_exp':
            return Name(Ident(asToken(t.children[0]).value)) # type: ignore
        case kind: # type: ignore
            raise Exception(f'unhandled parse tree of kind {kind} for exp: {t}')
        
def parseModule(args: ParserArgs) -> mod:
    parseTree = parseAsTree(args, grammarFile, 'lvar') # type: ignore
    ast = parseTreeToModuleAst(parseTree) # type: ignore
    log.debug(f'AST: {ast}')
    return ast

def parseTreeToModuleAst(t: ParseTree) -> mod: # type: ignore
    stmts = [parseTreeToStmtAst(child) for child in t.children] # type: ignore
    return Module(stmts)

        
def parseTreeToStmtAst(t: ParseTree) -> stmt: # type: ignore
    match t.data: # type: ignore
        case 'var_assign_stmt':
            try:
                var = Ident(asToken(t.children[0].children[0]).value) # type: ignore
            except:
                var = Ident(asToken(t.children[0]).value) # type: ignore
            exp = parseTreeToExpAst(asTree(t.children[1])) # type: ignore
            return Assign(var, exp)
        case 'exp_stmt':
            exp = parseTreeToExpAst(asTree(t.children[0])) # type: ignore
            return StmtExp(exp)
        
def parseTreeToStmtListAst(t: ParseTree) -> list[stmt]: # type: ignore
    return [parseTreeToStmtAst(child) for child in t.children] # type: ignore
