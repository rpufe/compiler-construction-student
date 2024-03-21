from lang_var.var_ast import *
from common.wasm import *
import lang_var.var_tychecker as var_tychecker
from common.compilerSupport import *
import common.utils as utils

def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    #stmts=var_tychecker.tycheckModule(m)
    
    wasm_instr: list[WasmInstr]=[WasmInstrConst('i64', 1), WasmInstrCall(WasmId('$print_i64'))]
    main=WasmFunc(id=WasmId('main'), params=[], result=None, locals=[], instrs=wasm_instr)

    return WasmModule(imports=wasmImports(cfg.defaultMaxMemSize),
                      exports=[WasmExport(name='main', desc=WasmExportFunc(WasmId('$main')))],
                      globals=[],
                      data=[],
                      funcTable=WasmFuncTable(elems=[]),
                      funcs=[main])
