from lang_fun.fun_ast import *
import lang_fun.fun_astAtom as atom
from common.compilerSupport import *
import common.utils as utils

type Temporaries = list[tuple[atom.Ident, atom.exp]]

class Ctx:
    """
    Context for getting fresh variable names.
    """
    def __init__(self):
        self.freshVars: dict[ident, ty] = {}
    def newVar(self, t: ty) -> ident:
        """
        Get a fresh variabler of the given type.
        """
        nameId = len(self.freshVars)
        x = Ident(f'tmp_{nameId}')
        self.freshVars[x] = t
        return x

def transExpAtomic(e: exp, ctx: Ctx) -> tuple[atom.atomExp, Temporaries]:
    """
    Translates e to an atomic expression. Essentially a shortcut for transExp(e, True, ctx).
    """
    (res, ts) = transExp(e, True, ctx)
    match res:
        case atom.AtomExp(a):
            return (a, ts)
        case _:
            utils.abort(f'transExp with needAtom=True failed to return an atomic expression: {e}')

def assertExpNotVoid(e: exp | atom.exp) -> ty:
    """
    Asserts that e is an expression of a non-void type.
    """
    match e.ty:
        case None:
            raise ValueError(f'type still None after type-checking. Expression: {e}')
        case Void():
            raise ValueError(f'type of {e} is Void after type-checking.')
        case NotVoid(t):
            return t

def atomic(needAtomic: bool, e: atom.exp, tmps: Temporaries, ctx: Ctx) -> tuple[atom.exp, Temporaries]:
    """
    Converts e to an atomic expression if needAtomic is True.
    """
    if needAtomic:
        t = assertExpNotVoid(e)
        tmp = ctx.newVar(t)
        match e:
            case atom.Call():
                return (atom.AtomExp(atom.FunName(tmp, t), e.ty), tmps + [(tmp, e)])
            case _:
                return (atom.AtomExp(atom.VarName(tmp, t), e.ty), tmps + [(tmp, e)])
    else:
        return (e, tmps)

def transExp(e: exp, needAtomic: bool, ctx: Ctx) -> tuple[atom.exp, Temporaries]:
    """
    Translates expression e (of type fun_ast.exp) to an expression of type
    fun_astAtom.exp, together with a list of temporary variables used by
    the translated expression.

    If the flag needAtomic is True, then the translated expression is an atomic expression,
    that is something of the form fun_astAtom.AtomExp(...).
    """
    t = e.ty
    if t is None:
        raise ValueError(f'type still None after type-checking. Expression: {e}')
    match e:
        case IntConst(v):
            return (atom.AtomExp(atom.IntConst(v, Int()), t), [])
        case BoolConst(v):
            return (atom.AtomExp(atom.BoolConst(v, Bool()), t), [])
        case Call(id, args):
            match id:
                case Name():
                    (atomArgs, tmps) = utils.unzip([transExp(a, False, ctx) for a in args])
                    match id.scope:
                        case BuiltinFun():
                            fun_to_call = atom.CallTargetBuiltin(id.var)
                        case Var():
                            atomic_fun, tmps_fun = transExp(id, True, ctx)
                            var_name = atomic_fun.e.var # type: ignore
                            arg_types = [arg.ty.ty for arg in args if isinstance(arg.ty, NotVoid)]
                            fun_to_call = atom.CallTargetIndirect(var_name, arg_types, t) # type: ignore
                        case UserFun():
                            fun_to_call = atom.CallTargetDirect(id.var)
                        case _:
                            raise TypeError(f"scope {id.scope} not defined")
                    return atomic(needAtomic, atom.Call(fun_to_call, atomArgs, t), utils.flatten(tmps), ctx)
                case Subscript() | Call():
                    atom_fun, tmps_fun = transExp(id, True, ctx)
                    atom_args: list[atom.exp]  = []
                    args_tys: list[ty] = []
                    tmps_args: Temporaries = []
                    for arg in args:
                        atomic_arg, tmps_arg = transExp(arg, True, ctx)
                        atom_args.append(atomic_arg)
                        tmps_args.extend(tmps_arg)
                        if arg.ty is not None and isinstance(arg.ty, NotVoid):
                            args_tys.append(arg.ty.ty)
                    indirect = atom.CallTargetIndirect(tmps_fun[0][0], args_tys, atom_fun.ty.ty.result) # type: ignore
                    return atom.Call(indirect, atom_args, t), tmps_fun + tmps_args
                case _:
                    raise TypeError(f"call not implemented for {fun}")
        case UnOp(op, sub):
            (atomSub, tmps) = transExp(sub, False, ctx)
            return atomic(needAtomic, atom.UnOp(op, atomSub, t), tmps, ctx)
        case BinOp(left, op, right):
            (l, tmps1) = transExp(left, False, ctx)
            (r, tmps2) = transExp(right, False, ctx)
            return atomic(needAtomic, atom.BinOp(l, op, r, t), tmps1 + tmps2, ctx)
        case Name(x, scope):
            xt = assertExpNotVoid(e)
            match scope:
                case Var():
                    return (atom.AtomExp(atom.VarName(x, xt), t), [])
                case UserFun():
                    return (atom.AtomExp(atom.FunName(x, xt), t), [])
                case BuiltinFun():
                    return (atom.AtomExp(atom.VarName(x, xt), t), [])
                case _:
                    raise ValueError(f'Unknown scope: {scope}')
        case ArrayInitDyn(lenExp, elemInit):
            (atomLen, tmps1) = transExpAtomic(lenExp, ctx)
            (atomElem, tmps2) = transExpAtomic(elemInit, ctx)
            return atomic(needAtomic, atom.ArrayInitDyn(atomLen, atomElem, t), tmps1 + tmps2, ctx)
        case ArrayInitStatic(initExps):
            (atomArgs, tmps) = utils.unzip([transExpAtomic(i, ctx) for i in initExps])
            return atomic(needAtomic, atom.ArrayInitStatic(atomArgs, t), utils.flatten(tmps), ctx)
        case Subscript(arrExp, indexExp):
            (atomArr, tmps1) = transExpAtomic(arrExp, ctx)
            (atomIndex, tmps2) = transExpAtomic(indexExp, ctx)
            return atomic(needAtomic, atom.Subscript(atomArr, atomIndex, t), tmps1 + tmps2, ctx)

def mkAssigns(tmps: Temporaries) -> list[atom.stmt]:
    """
    Turns a list of temporary variables into a list of statements.
    """
    return [atom.Assign(x, e) for (x, e) in tmps]

def transStmt(s: stmt, ctx: Ctx) -> list[atom.stmt]:
    """
    Translates statement s (of type fun_ast.stmt) to a statement of type
    fun_astAtom.stmt.
    """
    match s:
        case StmtExp(e):
            (a, tmps) = transExp(e, False, ctx)
            return mkAssigns(tmps) + [atom.StmtExp(a)]
        case Assign(x, e):
            (a, tmps) = transExp(e, False, ctx)
            return mkAssigns(tmps) + [atom.Assign(x, a)]
        case IfStmt(cond, thenBody, elseBody):
            (a, tmps1) = transExp(cond, False, ctx)
            stmts1, _ = transStmts(thenBody, ctx)
            stmts2, _ = transStmts(elseBody, ctx)
            return mkAssigns(tmps1) + [atom.IfStmt(a, stmts1, stmts2)]
        case WhileStmt(cond, body):
            (a, tmps1) = transExp(cond, False, ctx)
            stmts, _ = transStmts(body, ctx)
            return mkAssigns(tmps1) + [atom.WhileStmt(a, stmts)]
        case SubscriptAssign(leftExp, indexExp, rightExp):
            (l, tmps1) = transExpAtomic(leftExp, ctx)
            (i, tmps2) = transExpAtomic(indexExp, ctx)
            (r, tmps3) = transExp(rightExp, False, ctx)
            return mkAssigns(tmps1 + tmps2 + tmps3) + [atom.SubscriptAssign(l, i, r)]
        case Return(res):
            if res is not None:
                (a, tmps) = transExp(res, False, ctx)
                return mkAssigns(tmps) + [atom.Return(a)]
            return [atom.Return(None)]

def transStmts(stmts: list[stmt], ctx: Ctx) -> tuple[list[atom.stmt], Ctx]:
    """
    Main entry point, transforming a list of statements.
    This function is called from compilers.array_compiler.compileModule.
    """
    result: list[atom.stmt] = []
    for s in stmts:
        result.extend(transStmt(s, ctx))
    return result, ctx