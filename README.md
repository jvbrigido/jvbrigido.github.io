# Portal João Brígido

Portal de conteúdo médico de João Brígido, médico, CRM 52-1088629 RJ. Site estático hospedado no GitHub Pages e construído segundo o *Guia Mestre de Construção do Portal João Brígido* (v1.0, outubro de 2026). Mantido pelo setor Blogueiro do Projeto Cuco; decisões e preferências ficam no Google Drive (Projeto Cuco / 05 - Blogueiro).

## Como o site é gerado

O conteúdo e o visual ficam em `fonte/`. As páginas na raiz do repositório são geradas a partir dela e não devem ser editadas à mão.

```
python3 fonte/gerar.py                      # site público: só artigos com "status: aprovado"
python3 fonte/gerar.py --revisao SAIDA --rascunhos PASTA   # ambiente privado de revisão
```

Requer Python 3 com `jinja2`, `markdown` e `pyyaml`.

| Pasta ou arquivo | Conteúdo |
|---|---|
| `fonte/site.yml` | Identificação, contatos, consultório, temas da biblioteca e pendências (um ponto único) |
| `fonte/artigos/` | Artigos aprovados, um `.md` por artigo, com cabeçalho YAML |
| `fonte/paginas/` | Política editorial, Privacidade e Termos de uso |
| `fonte/templates/` | Modelos das páginas (Jinja2) |
| `fonte/assets/` | CSS, JavaScript, fontes (licença OFL) e imagens |

## Regras que o gerador respeita

- Rascunhos não entram neste repositório, que é público. Só artigos aprovados pelo João são publicados.
- Enquanto `lancado: false` em `site.yml`, todas as páginas saem com `noindex`.
- Sem formulários, cookies, estatísticas ou rastreadores; fontes e imagens hospedadas no próprio site.
- Nenhuma especialidade é anunciada sem RQE conferido (Resolução CFM nº 2.336/2023).
