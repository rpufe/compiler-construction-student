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
                instrs=instrs+compileExp(e)
            case Assign(x, e):
                instrs=instrs+compileExp(e)+[WasmInstrVarLocal(op='set', id=WasmId(id=f'${x.name}'))]
            case IfStmt(cond, tb, eb):
                pass
            case WhileStmt(cond, b):
                pass

    return instrs

def compileExp(exp: exp) -> list[WasmInstr]:
    match exp:
        case IntConst(n):
            return [WasmInstrConst(ty='i64', val=n)]
        case BoolConst(n):
            return [WasmInstrConst(ty='i32', val=n)]
        case Name(x):
            return [WasmInstrVarLocal(op='get', id=WasmId(id=f'${x.name}'))]
        case Call(x, args):
            a: list[WasmInstr]=[]
            for e in args:
                a=a+compileExp(e)
            if 'print' in x.name:
                name: str='print_i64'
            elif 'input' in x.name:
                name: str='input_i64'
            else:
                name: str=x.name
            a=a+[WasmInstrCall(id=WasmId(id=f'${name}'))]
            return a
        case UnOp(_, arg):
            return [WasmInstrConst(ty='i64', val=0)]+compileExp(arg)+[WasmInstrNumBinOp(ty='i64', op='sub')]
        case BinOp(left, op, right):
            if type(op)==Add:
                wasmOP: str='add'
            elif type(op)==Sub:
                wasmOP: str='sub'
            else:
                wasmOP:str='mul'
            return compileExp(left)+compileExp(right)+[WasmInstrNumBinOp(ty='i64', op=wasmOP)]

def identToWasmId(id: Ident) -> WasmId:
    return WasmId(id=f'${id.name}')

def tyOfExp(e: exp) -> ty:
    if e.ty!=None:
        return e.ty
    else:
        raise CompileError.typeError(f'')