def get_name_for_ordering(name: str) -> str:
    name = name.strip()
    if name.endswith(')'):
        ix = name.index("(")
        name = name[:ix-1].strip()
    remove_these_suffixes = [
        "the Serb",
        "the younger",
        "the Younger",
        "the elder",
        "the Elder",
    ]
    for removable in remove_these_suffixes:
        name = name.removesuffix(removable)
    split_name = name.split()
    if len(split_name) >= 3 and split_name[-2] == "of":
        return split_name[0]
    for word in ["the", "of"]:
        if word in split_name:
            print(name)
    return split_name[-1]
