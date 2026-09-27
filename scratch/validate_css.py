import sys

def check_css_braces(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    stack = []
    line_no = 1
    col_no = 1
    in_comment = False
    in_string = False
    string_char = ''
    i = 0
    n = len(content)

    while i < n:
        char = content[i]
        if char == '\n':
            line_no += 1
            col_no = 1
            i += 1
            continue

        if not in_comment and not in_string:
            if i + 1 < n and content[i:i+2] == '/*':
                in_comment = True
                i += 2
                col_no += 2
                continue
            elif char in ('"', "'"):
                in_string = True
                string_char = char
                i += 1
                col_no += 1
                continue
            elif char == '{':
                stack.append((line_no, col_no))
            elif char == '}':
                if not stack:
                    print(f"Error: Unexpected closing brace '}}' at line {line_no}:{col_no}")
                    return False
                stack.pop()
        elif in_comment:
            if i + 1 < n and content[i:i+2] == '*/':
                in_comment = False
                i += 2
                col_no += 2
                continue
        elif in_string:
            if char == '\\':
                i += 2
                col_no += 2
                continue
            elif char == string_char:
                in_string = False

        i += 1
        col_no += 1

    if in_comment:
        print("Error: Unclosed comment in CSS")
        return False
    if in_string:
        print("Error: Unclosed string in CSS")
        return False
    if stack:
        print(f"Error: {len(stack)} unclosed opening brace(s) '{{'. First unclosed at line {stack[0][0]}:{stack[0][1]}")
        return False

    print("Success: All CSS braces, comments, and strings are balanced perfectly!")
    return True

if __name__ == '__main__':
    result = check_css_braces('website/static/css/style.css')
    sys.exit(0 if result else 1)
