def apply_result(state, generation, value):
    if generation != state["generation"]:
        return False

    state["result"] = value
    return True
