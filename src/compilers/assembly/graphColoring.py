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
    to a TACspill variable. You have to implement the "simple graph coloring algorithm"
    from slide 58 here.

    - Parameter maxRegs is the maximum number of registers we are allowed to use.
    - Parameter secondaryOrder is used by the tests to get deterministic results even
      if two variables have the same number of forbidden colors.
    """
    log.debug(f"Coloring interference graph with maxRegs={maxRegs}")
    colors: dict[tac.ident, int] = {}
    forbidden: dict[tac.ident, set[int]] = {}
    q = PrioQueue(secondaryOrder)
    
    # for v in g.vertices:
    #     degree = len(g.succs(v))
    #     q.push(v, degree)
    
    # while not q.isEmpty():
    #     x = q.pop()
    #     forbidden[x] = set()

    #     for neighbor in g.succs(x):
    #         if neighbor in colors:
    #             forbidden[x].add(colors[neighbor])

    #     chosen_color = chooseColor(x, forbidden, maxRegs)
    #     if chosen_color >= maxRegs:
    #         chosen_color = maxRegs + len(colors)
        
    #     colors[x] = chosen_color

    #     for neighbor in g.succs(x):
    #         if neighbor not in forbidden:
    #             forbidden[neighbor] = set()
    #         forbidden[neighbor].add(chosen_color)

    spillStack: list[tac.ident] = []

    # Step 2: Push all nodes into the priority queue with priority based on their degree
    for v in g.vertices:
        degree = len(g.succs(v))
        q.push(v, degree)
    
    # Step 3: Simplify phase - process nodes in order of decreasing degree
    while not q.isEmpty():
        x = q.pop()
        forbidden[x] = set()

        # Update forbidden colors based on neighbors' colors
        for neighbor in g.succs(x):
            if neighbor in colors:
                forbidden[x].add(colors[neighbor])

        # Choose the lowest possible color that is not forbidden
        chosen_color = chooseColor(x, forbidden, maxRegs)
        
        if chosen_color >= maxRegs:
            # Spill logic: mark this variable to be spilled
            spillStack.append(x)
        else:
            colors[x] = chosen_color

    # Step 4: Handle spills by assigning spill slots
    spillOffset = maxRegs
    for x in spillStack:
        colors[x] = spillOffset
        spillOffset += 1

    m = RegisterAllocMap(colors, maxRegs)
    return m
