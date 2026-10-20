#!/usr/bin/env python3
"""Gera o Portal João Brígido, um site estático, a partir da pasta fonte/.

Produção (site público, só conteúdo aprovado, escreve na raiz do repositório):
    python3 fonte/gerar.py

Revisão (ambiente privado para aprovação, inclui rascunhos e pendências):
    python3 fonte/gerar.py --revisao /caminho/saida --rascunhos /caminho/com/rascunhos

Artigos: um arquivo .md por artigo, com cabeçalho YAML entre linhas '---'.
Só artigos com "status: aprovado" entram no site público. Rascunhos ficam fora
do repositório (o repositório é público) até a aprovação do João.
"""
import argparse
import datetime as dt
import math
import os
import re
import shutil
import unicodedata
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

FONTE = Path(__file__).resolve().parent
RAIZ = FONTE.parent
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
POR_PAGINA = 9  # cards por página de coleção (Guia Mestre, cap. 07)

AVISOS = {
    "suicidio": ("Se você está pensando em suicídio ou teme por alguém",
                 "Em situação de risco imediato, procure um serviço de urgência ou ligue 192 (SAMU). "
                 "Para conversar com alguém agora, o CVV atende pelo 188, 24 horas, gratuitamente. "
                 "O apoio emocional não substitui o atendimento de emergência."),
    "urgencia": ("Em situação urgente",
                 "Em situação de risco imediato, procure um serviço de urgência ou acione o SAMU pelo 192. "
                 "Para apoio emocional, o CVV atende pelo 188. O apoio emocional não substitui o atendimento de emergência."),
}


def slugify(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def data_extenso(iso):
    if not iso:
        return ""
    d = dt.date.fromisoformat(str(iso))
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def ler_markdown(caminho):
    texto = Path(caminho).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    if not m:
        raise SystemExit(f"Cabeçalho YAML ausente em {caminho}")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def md_para_html(corpo):
    md = markdown.Markdown(extensions=["tables", "sane_lists", "attr_list", "toc"],
                           extension_configs={"toc": {"slugify": lambda v, s: slugify(v), "toc_depth": "2"}})
    html = md.convert(corpo)
    toc = [{"id": t["id"], "texto": t["name"]} for t in md.toc_tokens]
    return html, toc


class Portal:
    def __init__(self, revisao_dir=None, rascunhos_dir=None):
        self.revisao = revisao_dir is not None
        self.saida = Path(revisao_dir) if self.revisao else RAIZ
        self.site = yaml.safe_load((FONTE / "site.yml").read_text(encoding="utf-8"))
        self.env = Environment(loader=FileSystemLoader(FONTE / "templates"), autoescape=True,
                               trim_blocks=True, lstrip_blocks=True)
        # links internos escritos no Markdown ("/contato/") passam pela mesma regra de caminhos dos modelos
        self.env.filters["links"] = lambda html, u: re.sub(
            r'href="(/[^"]*)"', lambda m: f'href="{u(m.group(1))}"', html)
        self.eixos = self.site["eixos"]
        for e in self.eixos:
            e["url"] = f"/biblioteca/{e['slug']}/"
        self.eixo_por_slug = {e["slug"]: e for e in self.eixos}
        self.artigos = self.carregar_artigos([FONTE / "artigos"] + ([Path(rascunhos_dir)] if rascunhos_dir else []))
        self.paginas_geradas = []
        self.preparar_consulta()

    # ---------- consulta e motivos de consulta (regras de publicação) ----------
    def preparar_consulta(self):
        """Res. CFM 2.336/2023, art. 11, I: um tema de atendimento só vai ao site público com o RQE correspondente.
        Na revisão, tudo aparece, com a indicação do que falta."""
        rqes = {r["titulo"] for r in self.site.get("rqe", [])}
        temas = []
        for t in self.site.get("temas_atendimento", []):
            liberado = bool(rqes & set(t.get("rqe", []))) and not t.get("confirmar")
            if not (liberado or self.revisao):
                continue
            temas.append({**t, "liberado": liberado,
                          "leituras_ok": [self.artigos[s] for s in t.get("leituras", []) if s in self.artigos]})
        self.temas = temas
        # o título "Dor, sono, foco e emoções" anuncia temas de psiquiatria: só com tema desse grupo liberado
        self.anuncio = self.revisao or any(t["liberado"] and t.get("grupo") == "psiquiatria" for t in temas)
        self.consulta_ok = self.revisao or self.site["consulta"].get("aprovado", False)
        self.trabalho_ok = self.revisao or self.site["como_trabalho"].get("aprovado", False)

    # ---------- conteúdo ----------
    def carregar_artigos(self, pastas):
        artigos = {}
        for pasta in pastas:
            for arq in sorted(Path(pasta).glob("*.md")):
                meta, corpo = ler_markdown(arq)
                status = meta.get("status", "rascunho")
                if status != "aprovado" and not self.revisao:
                    continue
                slug = meta.get("slug") or arq.stem
                eixo = self.eixo_por_slug[meta["eixo"]]
                corpo = re.sub(r"(?:\{ref:\d+(?:\s*,\s*\d+)*\})+", lambda m:'<sup class="ref">' + ",".join(
                    f'<a href="#ref-{n}" aria-label="Referência {n}">{n}</a>'
                    for n in re.findall(r"\d+", m.group(0))) + "</sup>", corpo)
                html, toc = md_para_html(corpo)
                aviso = meta.get("aviso")
                aviso_html = ""
                if aviso:
                    titulo, texto = AVISOS.get(aviso) or (meta.get("aviso_titulo", "Atenção"), meta.get("aviso_texto", ""))
                    aviso_html = (f'<aside class="aviso-seguranca" role="note"><p class="aviso-titulo">{titulo}</p>'
                                  f'<p>{texto}</p></aside>')
                if "<p>[[aviso]]</p>" in html:
                    html = html.replace("<p>[[aviso]]</p>", aviso_html)
                    aviso_html = ""
                palavras = len(re.sub(r"<[^>]+>", " ", html).split())
                artigos[slug] = {
                    **meta,
                    "slug": slug,
                    "status": status,
                    "eixo": eixo,
                    "url": f"/artigos/{slug}/",
                    "html": html,
                    "toc": toc if palavras > 600 and len(toc) >= 4 else [],
                    "aviso_topo": aviso_html,
                    "minutos": max(1, math.ceil(palavras / 200)),
                    "publicado_texto": data_extenso(meta.get("publicado")),
                    "revisado_texto": data_extenso(meta.get("revisado")),
                    "ordem": meta.get("ordem", 99),
                }
        return artigos

    def ordenados(self, lista):
        return sorted(lista, key=lambda a: (str(a.get("publicado") or "9999"), -a["ordem"]), reverse=True) \
            if any(a.get("publicado") for a in lista) else sorted(lista, key=lambda a: a["ordem"])

    def do_eixo(self, slug):
        lista = [a for a in self.artigos.values() if a["eixo"]["slug"] == slug]
        destaque = [a for a in lista if a.get("destaque_colecao")]
        resto = self.ordenados([a for a in lista if not a.get("destaque_colecao")])
        return destaque[:1] + destaque[1:] + resto

    # ---------- links ----------
    def link(self, atual):
        """Produção: caminhos a partir da raiz ('/biblioteca/'). Revisão: caminhos relativos com index.html."""
        def u(destino):
            if destino.startswith(("http://", "https://", "mailto:", "#")):
                return destino
            if not self.revisao:
                return destino
            caminho, _, ancora = destino.partition("#")
            alvo = caminho.lstrip("/")
            if alvo == "" or alvo.endswith("/"):
                alvo += "index.html"
            base = os.path.dirname(atual) or "."
            return os.path.relpath(alvo, base) + (f"#{ancora}" if ancora else "")
        return u

    def whatsapp(self, mensagem=None):
        from urllib.parse import quote
        c = self.site["contato"]
        return f"https://wa.me/{c['whatsapp_numero']}?text={quote(mensagem or c['whatsapp_mensagem'])}"

    # ---------- renderização ----------
    def render(self, template, caminho, secao, titulo, descricao, **ctx):
        u = self.link(caminho)
        canonical = self.site["url"] + ("/" + caminho[:-len("index.html")] if caminho.endswith("index.html") else "/" + caminho)
        html = self.env.get_template(template).render(
            site=self.site, eixos=self.eixos, revisao=self.revisao, u=u, secao=secao,
            titulo_pagina=titulo, descricao=descricao, canonical=canonical.replace("//index.html", "/"),
            noindex=self.revisao or not self.site.get("lancado"), whatsapp=self.whatsapp,
            esqueleto_artifact=self.revisao and caminho == "index.html", caminho=caminho,
            temas=self.temas, anuncio=self.anuncio, consulta=self.site["consulta"],
            consulta_ok=self.consulta_ok, trabalho_ok=self.trabalho_ok, **ctx)
        destino = self.saida / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
        self.paginas_geradas.append(caminho)

    def gerar(self):
        s = self.site
        nome = s["nome_publico"]
        artigos = list(self.artigos.values())
        comece = sorted([a for a in artigos if a.get("comece_por_aqui")], key=lambda a: a["comece_por_aqui"])[:3]
        recentes = [a for a in self.ordenados(artigos) if a not in comece][:6]

        # na revisão, a página inicial vira o nome do Artifact na galeria do Claude: só o nome do portal
        titulo_inicio = f"Portal {nome}" if self.revisao else f"{nome} · Saúde mental, dor e movimento"
        self.render("inicio.html", "index.html", "inicio", titulo_inicio,
                    "Portal de conteúdo médico de João Brígido sobre psiquiatria e saúde mental, dor e ortopedia e traumatologia, com explicações claras para o público leigo.",
                    comece=comece, recentes=recentes)

        por_eixo = {e["slug"]: self.do_eixo(e["slug"]) for e in self.eixos}
        self.render("biblioteca.html", "biblioteca/index.html", "biblioteca", f"Biblioteca · {nome}",
                    "Textos organizados em três temas: psiquiatria e saúde mental, dor, e ortopedia e traumatologia.",
                    por_eixo=por_eixo)

        for e in self.eixos:
            lista = por_eixo[e["slug"]]
            paginas = max(1, math.ceil(len(lista) / POR_PAGINA))
            for n in range(1, paginas + 1):
                caminho = f"biblioteca/{e['slug']}/index.html" if n == 1 else f"biblioteca/{e['slug']}/pagina/{n}/index.html"
                self.render("colecao.html", caminho, "biblioteca", f"{e['nome']} · Biblioteca · {nome}", e["intro"],
                            eixo=e, itens=lista[(n - 1) * POR_PAGINA:n * POR_PAGINA], pagina=n, paginas=paginas)

        for a in artigos:
            relacionados = [self.artigos[r] for r in a.get("relacionados", []) if r in self.artigos][:3]
            self.render("artigo.html", f"artigos/{a['slug']}/index.html", "biblioteca", f"{a['titulo']} · {nome}",
                        a["resumo"], a=a, relacionados=relacionados, og_tipo="article")

        self.render("sobre.html", "sobre/index.html", "sobre", f"Sobre · {nome}",
                    "Quem é João Brígido, médico, e por que este portal existe.")
        self.render("consultorio.html", "consultorio/index.html", "consultorio", f"Consultório · {nome}",
                    "Informações administrativas sobre o atendimento no consultório em Icaraí, Niterói.")
        self.render("contato.html", "contato/index.html", "contato", f"Contato · {nome}",
                    "Canais administrativos para informações sobre atendimento.")

        for arq in sorted((FONTE / "paginas").glob("*.md")):
            meta, corpo = ler_markdown(arq)
            html, _ = md_para_html(corpo)
            self.render("texto.html", f"{arq.stem}/index.html", "", f"{meta['titulo']} · {nome}", meta["descricao"],
                        pagina_meta=meta, conteudo=html)

        self.render("404.html", "404.html", "", f"Página não encontrada · {nome}",
                    "A página procurada não foi encontrada.")
        self.copiar_assets()
        if not self.revisao:
            self.mapa_e_robots()
        return self.paginas_geradas

    def copiar_assets(self):
        destino = self.saida / "assets"
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(FONTE / "assets", destino)

    def mapa_e_robots(self):
        urls = [self.site["url"] + "/" + p[:-len("index.html")] for p in self.paginas_geradas if p.endswith("index.html")]
        corpo = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
        (self.saida / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{corpo}\n</urlset>\n',
            encoding="utf-8")
        (self.saida / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\nSitemap: {self.site['url']}/sitemap.xml\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisao", help="pasta de saída do ambiente de revisão (privado)")
    ap.add_argument("--rascunhos", help="pasta com artigos em rascunho (só na revisão)")
    a = ap.parse_args()
    if a.rascunhos and not a.revisao:
        raise SystemExit("Rascunhos só entram no ambiente de revisão (--revisao).")
    geradas = Portal(a.revisao, a.rascunhos).gerar()
    print(f"{len(geradas)} páginas geradas em {a.revisao or RAIZ}")
