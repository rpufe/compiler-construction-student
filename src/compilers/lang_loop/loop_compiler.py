from lang_loop.loop_ast import *
from common.wasm import *
import lang_loop.loop_tychecker as var_tychecker
from common.compilerSupport import *
# import common.utils as utils
from common.compilerSupport import *


def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = var_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    # instrs = [instr for instr in instrs if not isinstance(instr, WasmInstrDrop)]
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), 'i64' if type(xty)==Int else 'i32') for x, xty in vars.types()] # [(identToWasmId(x), 'i64') for x in vars]

    return WasmModule(imports=wasmImports(cfg.maxMemSize),
                      exports=[WasmExport("main", WasmExportFunc(idMain))],
                      globals=[],
                      data=[],
                      funcTable=WasmFuncTable([]),
                      funcs=[WasmFunc(idMain, [], None, locals, instrs)])

def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    
    instrs : list[WasmInstr]=[]
    for stmt in stmts:
        match stmt:
            case StmtExp(e):
                instrs+=compileExp(e)
            case Assign(x, e):
                instrs+=compileExp(e)+[WasmInstrVarLocal(op='set', id=WasmId(id=f'${x.name}'))]
            case IfStmt(cond, tb, eb):
                # instrs+=compileExp(cond)+[WasmInstrIf(resultType='i32', thenInstrs=compileStmts(tb)+[WasmInstrConst(ty='i32', val=0)], elseInstrs=compileStmts(eb)+[WasmInstrConst(ty='i32', val=0)])]+[WasmInstrDrop()]
                instrs+=compileExp(cond)+[WasmInstrIf(resultType=None, thenInstrs=compileStmts(tb), elseInstrs=compileStmts(eb))]
            case WhileStmt(cond, b):
                instrs+=compileWhile(cond, b)

    return instrs

def compileExp(exp: exp) -> list[WasmInstr]:
    match exp:
        case IntConst(n):
            return [WasmInstrConst(ty='i64', val=n)]
        case BoolConst(n):
            match n:
                case True:
                    return [WasmInstrConst(ty='i32', val=1)]
                case False:
                    return [WasmInstrConst(ty='i32', val=0)]
        case Name(x):
            return [WasmInstrVarLocal(op='get', id=WasmId(id=f'${x.name}'))]
        case Call(x, args):
            a: list[WasmInstr]=[]
            for e in args:
                a=a+compileExp(e)
            if 'print' in x.name:
                match tyOfExp(args[0]):
                    case Bool():
                        name: str='$print_i64'
                    case Int():
                        name: str='$print_i64'
            elif 'input' in x.name:
                name: str='$input_i64'
            else:
                name: str=x.name
            a=a+[WasmInstrCall(id=WasmId(id=name))]
            return a
        case UnOp(op, arg):
            match op:
                case USub():
                    return [WasmInstrConst(ty='i64', val=0)]+compileExp(arg)+[WasmInstrNumBinOp(ty='i64', op='sub')]
                case Not():
                    return compileExp(arg)+[WasmInstrConst(ty='i32', val=0), WasmInstrIntRelOp(ty='i32', op='eq')]
        case BinOp(left, op, right):
            match op:
                case Add():
                    return compileExp(left)+compileExp(right)+[WasmInstrNumBinOp(ty='i64', op='add')]
                case Sub():
                    return compileExp(left)+compileExp(right)+[WasmInstrNumBinOp(ty='i64', op='sub')]
                case Mul():
                    return compileExp(left)+compileExp(right)+[WasmInstrNumBinOp(ty='i64', op='mul')]
                case Less():
                    return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i64', op='lt_s')]
                case LessEq():
                    return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i64', op='le_s')]
                case Greater():
                    return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i64', op='gt_s')]
                case GreaterEq():
                    return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i64', op='ge_s')]
                case Eq():
                    match tyOfExp(left):
                        case Bool():
                            return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i32', op='eq')]
                        case Int():
                            return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i64', op='eq')]
                case NotEq():
                    match tyOfExp(left):
                        case Bool():
                            return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i32', op='ne')]
                        case Int():
                            return compileExp(left)+compileExp(right)+[WasmInstrIntRelOp(ty='i64', op='ne')]
                case And():
                    return compileExp(left)+[WasmInstrIf(resultType='i32', thenInstrs=compileExp(right), elseInstrs=[WasmInstrConst(ty='i32', val=0)])]
                case Or():
                    return compileExp(left)+[WasmInstrIf(resultType='i32', thenInstrs=[WasmInstrConst(ty='i32', val=1)], elseInstrs=compileExp(right))]
                
def compileWhile(cond: exp, body: list[stmt]) -> list[WasmInstr]:
    instrs : list[WasmInstr]=[]

    start_label= WasmId('$loop_start')
    end_label=WasmId('$loop_end')

    # instrs+=[WasmInstrBlock(label=end_label, result=None, body=[WasmInstrLoop(label=start_label, body=compileExp(cond)+[WasmInstrIf(resultType='i32', thenInstrs=compileStmts(body)+[WasmInstrBranch(target=start_label, conditional=False)], elseInstrs=[WasmInstrBranch(target=end_label, conditional=False)]), WasmInstrDrop()])])]
    instrs+=[WasmInstrBlock(label=end_label, result=None, body=[WasmInstrLoop(label=start_label, body=compileExp(cond)+[WasmInstrIf(resultType=None, thenInstrs=compileStmts(body)+[WasmInstrBranch(target=start_label, conditional=False)], elseInstrs=[WasmInstrBranch(target=end_label, conditional=False)])])])]
    # loop_body: list[WasmInstr]=[WasmInstrLoop(label=start_label, body=compileExp(cond)+[WasmInstrIf(resultType=None, thenInstrs=[], elseInstrs=[WasmInstrBranch(target=end_label, conditional=False)])] + compileStmts(body) +[WasmInstrBranch(target=start_label, conditional=False)])]
    # instrs+=[WasmInstrBlock(label=end_label, result=None, body=loop_body)]

    return instrs

def identToWasmId(id: Ident) -> WasmId:
    return WasmId(id=f'${id.name}')

def tyOfExp(e: exp) -> ty:
    match e.ty:
        case None:
            raise ValueError
        case Void():
            raise ValueError
        case NotVoid(rty):
            return rty