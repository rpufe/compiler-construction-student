from assembly.common import *
from assembly.graph import Graph
import assembly.tac_ast as tac

def instrDef(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers defined by some instrucution.
    """
    if isinstance(instr, tac.Assign):
        return {instr.var}
    elif isinstance(instr, tac.Call):
        if instr.name.name == "$input_i64":
            var: Optional[tac.ident] = instr.var
            if var is not None:
                return {var}
        return set()
    return set()

def instrUse(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers used by some instruction.
    """
    uses: set[tac.ident] = set()
    if isinstance(instr, tac.Assign):
        if isinstance(instr.left, tac.Prim):
            if isinstance(instr.left.p, tac.Name):
                uses.add(instr.left.p.var)
        else:
            if isinstance(instr.left.left, tac.Name):
                uses.add(instr.left.left.var)
            if isinstance(instr.left.right, tac.Name):
                uses.add(instr.left.right.var)
    elif isinstance(instr, tac.Call):
        for arg in instr.args:
            if isinstance(arg, tac.Name):
                uses.add(arg.var)
    elif isinstance(instr, tac.GotoIf):
        if isinstance(instr.test, tac.Name):
            uses.add(instr.test.var)
    return uses

# Each individual instruction has an identifier. This identifier is the tuple
# (index of basic block, index of instruction inside the basic block)
type InstrId = tuple[int, int]

class InterfGraphBuilder:
    def __init__(self):
        # self.before holds, for each instruction I, to set of variables live before I.
        self.before: dict[InstrId, set[tac.ident]] = {}
        # self.after holds, for each instruction I, to set of variables live after I.
        self.after: dict[InstrId, set[tac.ident]] = {}

    def __liveStart(self, bb: BasicBlock, s: set[tac.ident]) -> set[tac.ident]:
        """
        Given a set of variables s and a basic block bb, __liveStart computes
        the set of variables live at the beginning of bb, assuming that s
        are the variables live at the end of the block.

        Essentially, you have to implement the subalgorithm "Computing L_start" from
        slide 46 here. You should update self.after and self.before while traversing
        the instructions of the basic block in reverse.
        """
        instructions = bb.instrs
        n = len(instructions)
        Lafter = [set() for _ in range(n + 1)] # type: ignore
        Lbefore = [set() for _ in range(n + 1)] # type: ignore
        Lafter[n] = s

        for k in range(n - 1, -1, -1):
            instr = instructions[k]
            defs = instrDef(instr)
            uses = instrUse(instr)
            Lbefore[k + 1] = (Lafter[k + 1] - defs) | uses
            Lafter[k] = Lbefore[k + 1]
            self.after[(bb.index, k)] = Lafter[k + 1]
            self.before[(bb.index, k)] = Lbefore[k + 1]

        return Lbefore[1] if n > 0 else set() # type: ignore

    def __liveness(self, g: ControlFlowGraph):
        """
        This method computes liveness information and fills the sets self.before and
        self.after.

        You have to implement the algorithm for computing liveness in a CFG from
        slide 46 here.
        """
        IN = {block: set() for block in g.vertices} # type: ignore
        OUT = {block: set() for block in g.vertices} # type: ignore

        changed = True
        while changed:
            changed = False
            for block in reversed(list(g.vertices)):
                new_out = set().union(*(IN[succ] for succ in g.succs(block))) # type: ignore
                if new_out != OUT[block]:
                    OUT[block] = new_out
                    changed = True
                new_in = self.__liveStart(g.getData(block), OUT[block]) # type: ignore
                if new_in != IN[block]:
                    IN[block] = new_in
                    changed = True

    def __addEdgesForInstr(self, instrId: InstrId, instr: tac.instr, interfG: InterfGraph):
        """
        Given an instruction and its ID, adds the edges resulting from the instruction
        to the interference graph.

        You should implement the algorithm specified on the slide
        "Computing the interference graph" (slide 50) here.
        """

        live = self.after[instrId]
        defs = instrDef(instr)
        for d in defs:
            if not interfG.hasVertex(d):
                interfG.addVertex(d, None)
            for v in live:
                if isinstance(instr, tac.Assign):
                    if isinstance(instr.left, tac.Prim) and isinstance(instr.left.p, tac.Name):
                        if instr.var == d and instr.left.p.var == v:
                            continue
                if d != v:
                    if not interfG.hasVertex(v):
                        interfG.addVertex(v, None)
                    interfG.addEdge(d, v)

    def build(self, g: ControlFlowGraph) -> InterfGraph:
        """
        This method builds the interference graph. It performs three steps:

        - Use __liveness to fill the sets self.before and self.after.
        - Setup the interference graph as an undirected graph containing all variables
          defined or used by any instruction of any basic block. Initially, the
          graph does not have any edges.
        - Use __addEdgesForInstr to fill the edges of the interference graph.
        """
        self.__liveness(g)
        
        interfG = Graph('undirected') # type: ignore

        all_vars = set() # type: ignore
        for block in g.vertices:
            bb = g.getData(block)
            for instr in bb.instrs:
                all_vars.update(instrDef(instr)) # type: ignore
                all_vars.update(instrUse(instr)) # type: ignore
        
        for var in all_vars: # type: ignore
            interfG.addVertex(var, None) # type: ignore

        for block in g.vertices:
            bb = g.getData(block)
            for i, instr in enumerate(bb.instrs):
                instrId = (bb.index, i)
                self.__addEdgesForInstr(instrId, instr, interfG) # type: ignore
        
        return interfG # type: ignore

def buildInterfGraph(g: ControlFlowGraph) -> InterfGraph:
    builder = InterfGraphBuilder()
    return builder.build(g)
