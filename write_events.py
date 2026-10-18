import pathlib

content = open(r'c:/Users/gamag/OneDrive/Área de Trabalho/vendas-de-sistemas/src/vendas/domain/events.py', 'r', encoding='utf-8').read()
pathlib.Path(r'c:/Users/gamag/OneDrive/Área de Trabalho/vendas-de-sistemas/src/vendas/domain/events.py').write_text(content, encoding='utf-8')
print('Done')