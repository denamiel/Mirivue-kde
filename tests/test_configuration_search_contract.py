"""Cross-check the real page caption and the existing GUI validation assertion.

This test evaluates the assertion expression without Qt. It does not replace
check_window's full graphical search/filter/selection checks.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(os.environ.get('MIRIVUE_CONTRACT_ROOT', Path(__file__).resolve().parents[1]))


class TestConfigurationSearchContract(unittest.TestCase):
    def test_search_contract_accepts_the_actual_configuration_page_title(self):
        tree = ast.parse((ROOT/'mirivue/configuration.py').read_text(encoding='utf-8'))
        page = next(node for node in ast.walk(tree)
                    if isinstance(node,ast.FunctionDef) and node.name=='_columns_page')
        call = next(node for node in ast.walk(page)
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                    and node.func.attr=='add_page')
        caption = ast.literal_eval(call.args[0].args[0])
        contract = ast.parse((ROOT/'mirivue/ui_contract.py').read_text(encoding='utf-8'))
        check = next(node for node in ast.walk(contract)
                     if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                     and node.func.id=='require' and len(node.args)>1
                     and isinstance(node.args[1],ast.Constant)
                     and node.args[1].value=='la recherche ne sélectionne pas la rubrique trouvée')
        expression=ast.Expression(body=check.args[0])
        dialog=SimpleNamespace(page_title=SimpleNamespace(text=lambda:caption))
        self.assertTrue(eval(compile(expression,'ui_contract.py','eval'),{'dialog':dialog}),
                        f'Le contrôle graphique refuse le titre réel : {caption!r}')


if __name__=='__main__': unittest.main()
