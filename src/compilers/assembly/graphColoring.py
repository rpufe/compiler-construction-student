from assembly.common import *
import assembly.tac_ast as tac
import common.log as log
from common.prioQueue import PrioQueue

def chooseColor(x: tac.ident, forbidden: dict[tac.ident, set[int]], maxRegs: int) -> int:
    """
    Returns the lowest possible color for variable x that is not forbidden for x.
    """
    forbidden_colors = forbidden.get(x, set())
    for color in range(maxRegs):
        if color not in forbidden_colors:
            return color
    return maxRegs

def colorInterfGraph(g: InterfGraph, secondaryOrder: dict[tac.ident, int]={},
                     maxRegs: int=MAX_REGISTERS) -> RegisterMap:
    """
    Given an interference graph, computes a register map mapping a TAC variable
    to a TACspill variable. Implements the graph coloring algorithm with spilling.

    - Parameter maxRegs is the maximum number of registers we are allowed to use.
    - Parameter secondaryOrder is used by the tests to get deterministic results even
      if two variables have the same number of forbidden colors.
    """
    log.debug(f"Coloring interference graph with maxRegs={maxRegs}")
    colors: dict[tac.ident, int] = {}
    forbidden: dict[tac.ident, set[int]] = {}
    q = PrioQueue(secondaryOrder)

    for v in g.vertices:
        q.push(v)
    
    while not q.isEmpty():
        x = q.pop()
        forbidden[x] = set()

        for neighbor in g.succs(x):
            if neighbor in colors:
                forbidden[x].add(colors[neighbor])

        chosen_color = chooseColor(x, forbidden, maxRegs)
        
        colors[x] = chosen_color

    m = RegisterAllocMap(colors, maxRegs)
    return m
