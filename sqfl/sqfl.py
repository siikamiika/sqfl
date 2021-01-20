from . import sp

class SqliteFilterParser:

    def __init__(self):
        self._var_counter = 0

        _fy = lambda f, y: lambda x: f(x, y)
        fx = lambda f, x: f(x)
        def reduce(x, fs):
            for f in fs: x = f(x)
            return x

        self.parser = sp.compile(r"""

            null = r'null' :                      `lambda x: {'type': 'null', 'val': None}` ;
            ident = r'[a-zA-Z_][a-zA-Z0-9_\.]*' : `lambda x: {'type': 'ident', 'name': x}` ;
            var = r'\?' :                         `self._var` ;
            real = r'\d+\.\d*|\d*\.\d+' :         `lambda x: {'type': 'real', 'val': float(x)}` ;
            int = r'\d+' :                        `lambda x: {'type': 'int', 'val': int(x)}` ;
            str = r"'((?:\\.|[^'\\])*)'" :        `self._str` ;

            add_op = '+'           `lambda x, y: {'type': '+', 'left': x, 'right': y}` ;
            add_op = '-'           `lambda x, y: {'type': '-', 'left': x, 'right': y}` ;
            add_op = '>>'          `lambda x, y: {'type': '>>', 'left': x, 'right': y}` ;
            add_op = '<<'          `lambda x, y: {'type': '<<', 'left': x, 'right': y}` ;
            add_op = '&'           `lambda x, y: {'type': '&', 'left': x, 'right': y}` ;
            add_op = '|'           `lambda x, y: {'type': '|', 'left': x, 'right': y}` ;
            add_op = '<'           `lambda x, y: {'type': '<', 'left': x, 'right': y}` ;
            add_op = '<='          `lambda x, y: {'type': '<=', 'left': x, 'right': y}` ;
            add_op = '>'           `lambda x, y: {'type': '>', 'left': x, 'right': y}` ;
            add_op = '>='          `lambda x, y: {'type': '>=', 'left': x, 'right': y}` ;
            add_op = '^'           `lambda x, y: {'type': '^', 'left': x, 'right': y}` ;
            add_op = '='           `lambda x, y: {'type': '=', 'left': x, 'right': y}` ;
            add_op = '=='          `lambda x, y: {'type': '=', 'left': x, 'right': y}` ;
            add_op = '!='          `lambda x, y: {'type': '!=', 'left': x, 'right': y}` ;
            add_op = 'is'          `lambda x, y: {'type': 'is', 'left': x, 'right': y}` ;
            add_op = 'is not'      `lambda x, y: {'type': 'is not', 'left': x, 'right': y}` ;
            add_op = 'like'        `lambda x, y: {'type': 'like', 'left': x, 'right': y}` ;
            add_op = 'regexp'      `lambda x, y: {'type': 'regexp', 'left': x, 'right': y}` ;
            add_op = 'and'         `lambda x, y: {'type': 'and', 'left': x, 'right': y}` ;
            add_op = 'or'          `lambda x, y: {'type': 'or', 'left': x, 'right': y}` ;

            mul_op = '||'          `lambda x, y: {'type': '||', 'left': x, 'right': y}` ;
            mul_op = '*'           `lambda x, y: {'type': '*', 'left': x, 'right': y}` ;
            mul_op = '/'           `lambda x, y: {'type': '/', 'left': x, 'right': y}` ;
            mul_op = '%'           `lambda x, y: {'type': '%', 'left': x, 'right': y}` ;

            un_op = '-'            `lambda x: {'type': '-', 'expr': x}` ;
            un_op = '+'            `lambda x: {'type': '+', 'expr': x}` ;
            un_op = '~'            `lambda x: {'type': '~', 'expr': x}` ;
            un_op = 'not'          `lambda x: {'type': 'not', 'expr': x}` ;

            exists_op = 'exists'   `lambda x, y: {'type': 'exists', 'path': x, 'expr': y}` ;

            separator: r'\s+';

            !S = expr ;

            expr = term (add_op term :: `_fy`)* :: `reduce` ;
            term = fact (mul_op fact :: `_fy`)* :: `reduce` ;
            fact = un_op fact :: `fx` | atom ;
            fact = exists_op ident atom :: `lambda f, x, y: f(x, y)` ;

            atom = '(' expr ')' ;
            atom = real | int ;
            atom = str ;
            atom = var ;
            atom = null ;
            atom = ident ;
        """)

    def _clean(self):
        sp.clean()
        self._var_counter = 0

    def _var(self, *args):
        seq = self._var_counter
        self._var_counter += 1
        return {'type': 'var', 'seq': seq}

    def _str(self, text):
        out = []
        escaped = False
        for c in text:
            if escaped:
                if c in ["'", '\\']:
                    out.append(c)
                else:
                    raise Exception(f'Invalid escape: {c}')
                escaped = False
                continue
            if c == '\\':
                escaped = True
                continue
            out.append(c)
        return {'type': 'str', 'val': ''.join(out)}

    def parse(self, text):
        self._clean()
        return self.parser(text)

class SqliteFilterCompiler:
    BINARY_OPS = {'+', '-', '>>', '<<', '&', '|', '<', '<=', '>', '>=', '^', '=', '!=', 'is', 'is not', 'like', 'regexp', 'and', 'or', '||', '*', '/', '%'}
    UNARY_OPS = {'-', '+', '~', 'not'}
    VARS = {'real', 'int', 'str'} # TODO explicit var
    IDENTS = {'ident'}
    NULLS = {'null'}
    EXISTS_OPS = {'exists'}

    def __init__(self, schema):
        self._schema = schema
        self._pivot_map = self._gen_pivot_map()

    def _validate_path(self, path):
        if len(path) == 0:
            return False
        i = 0
        while i < len(path):
            if path[i] not in self._schema:
                return False
            if i > 0 and path[i] not in self._schema[path[i - 1]]['children']:
                return False
            i += 1
        return True

    def _gen_pivot_map(self):
        pivot_map = {}
        for table_name, table_data in self._schema.items():
            if len(table_data['parents']) < 2: continue
            for foreign_table in table_data['parents']:
                pivot_table_name = '_'.join(sorted([foreign_table, table_name]))
                pivot_map[(foreign_table, table_name)] = pivot_table_name
                pivot_map[(table_name, foreign_table)] = pivot_table_name
        return pivot_map

    def compile(self, path, root_id, filter_ast):
        if not self._validate_path(path):
            raise Exception('Invalid path:', path)
        selects = [f'{t}.id AS _{t}_id' for t in path[:-1]] + [f'{path[-1]}.*']
        wheres = []
        params = []
        if root_id is not None:
            wheres.append(f'{path[0]}.id = ?')
            params.append(root_id)
        if filter_ast is not None:
            filter_where, filter_params = self._compile_filters(path, filter_ast)
            wheres.append(filter_where)
            params += filter_params
        return self._compile_sql_select(selects, path, wheres), params

    def _compile_sql_select(self, selects, path, wheres, pivot_table=None):
        froms = [path[0]]
        joins = []
        if pivot_table is not None:
            joins.append(f'JOIN {pivot_table} ON {froms[0]}.id = {pivot_table}.{froms[0]}_id')
        for table, parent_table in zip(path[1:], path[:-1]):
            pivot_table = self._pivot_map.get((table, parent_table))
            if pivot_table:
                joins.append(f'JOIN {pivot_table} ON {parent_table}.id = {pivot_table}.{parent_table}_id')
                joins.append(f'JOIN {table} ON {pivot_table}.{table}_id = {table}.id')
            else:
                joins.append(f'JOIN {table} ON {parent_table}.id = {table}.{parent_table}_id')

        selects_sql = ', '.join(selects)
        froms_sql = ', '.join(froms)
        joins_sql = ' '.join(joins)
        wheres_sql = '' if len(wheres) == 0 else 'WHERE ' + ' AND '.join(wheres)

        return f'SELECT {selects_sql} FROM {froms_sql} {joins_sql} {wheres_sql}'

    def _compile_filters(self, path, filter_ast):
        sql, params = self._compile_node(filter_ast, path)
        return sql, params

    def _compile_node(self, ast, path):
        if ast['type'] in SqliteFilterCompiler.BINARY_OPS:
            return self._compile_binary_op(ast, path)
        if ast['type'] in SqliteFilterCompiler.UNARY_OPS:
            return self._compile_unary_op(ast, path)
        if ast['type'] in SqliteFilterCompiler.VARS:
            return self._compile_var(ast, path)
        if ast['type'] in SqliteFilterCompiler.IDENTS:
            return self._compile_ident(ast, path)
        if ast['type'] in SqliteFilterCompiler.NULLS:
            return self._compile_null(ast, path)
        if ast['type'] in SqliteFilterCompiler.EXISTS_OPS:
            return self._compile_exists(ast, path)
        raise Exception('Unrecognized node:', ast['type'])

    def _compile_binary_op(self, ast, path):
        left, lparams = self._compile_node(ast['left'], path)
        right, rparams = self._compile_node(ast['right'], path)
        return f'({left} {ast["type"]} {right})', lparams + rparams

    def _compile_unary_op(self, ast, path):
        expr, params = self._compile_node(ast['expr'], path)
        return ast['type'] + ' ' + expr, params

    def _compile_var(self, ast, path):
        return '?', [ast['val']]

    def _compile_ident(self, ast, parent_path):
        *path, col = ast['name'].split('.')
        if not self._validate_path(path):
            raise Exception('Invalid path:', path)
        if col not in self._schema[path[-1]]['columns']:
            raise Exception('Invalid column:', col)
        if len(path) == 1 and path[0] in parent_path:
            return f'{path[0]}.{col}', []
        wheres, pivot_table = self._get_parent_details(path, parent_path)
        select_sql = self._compile_sql_select([f'{path[-1]}.{col}'], path, wheres, pivot_table)
        return f'({select_sql} LIMIT 1)', []

    def _compile_null(self, ast, path):
        return 'NULL', []

    def _get_parent_details(self, path, parent_path):
        # TODO exists from nested scope
        table = path[0]
        parent_table = parent_path[-1]
        if parent_table not in self._schema[table]['parents']:
            raise Exception('Invalid relationship:', (table, parent_table))

        pivot_table = self._pivot_map.get((parent_table, table))
        if pivot_table:
            wheres = [f'{pivot_table}.{parent_table}_id = {parent_table}.id']
        else:
            wheres = [f'{table}.{parent_table}_id = {parent_table}.id']
        return wheres, pivot_table

    def _compile_exists(self, ast, parent_path):
        # TODO maybe this shouldn't be a special case for generic ident
        path_node = ast['path']
        if path_node['type'] != 'ident':
            raise Exception('Invalid path:', path_node)
        path = path_node['name'].split('.')
        if not self._validate_path(path):
            raise Exception('Invalid path:', path)

        wheres, pivot_table = self._get_parent_details(path, parent_path)

        filter_where, filter_params = self._compile_node(ast['expr'], parent_path + path)
        wheres.append(filter_where)

        exists_sql = self._compile_sql_select(['*'], path, wheres, pivot_table)
        return f'{ast["type"]} ({exists_sql})', filter_params
