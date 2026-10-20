/* Portal João Brígido · menu do celular. Sem rastreamento, sem dependências. */
(function () {
  var raiz = document.documentElement;
  raiz.classList.add("js");
  var botao = document.querySelector(".menu-botao");
  var menu = document.getElementById("menu-principal");
  if (!botao || !menu) return;

  botao.hidden = false;

  function definir(aberto) {
    botao.setAttribute("aria-expanded", aberto ? "true" : "false");
    menu.classList.toggle("aberto", aberto);
  }

  botao.addEventListener("click", function () {
    definir(botao.getAttribute("aria-expanded") !== "true");
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && botao.getAttribute("aria-expanded") === "true") {
      definir(false);
      botao.focus();
    }
  });

  menu.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest("a")) definir(false);
  });

  var largo = window.matchMedia ? window.matchMedia("(min-width: 1081px)") : null;
  if (largo) {
    var aoMudar = function () { if (largo.matches) definir(false); };
    if (largo.addEventListener) largo.addEventListener("change", aoMudar);
    else if (largo.addListener) largo.addListener(aoMudar);
  }
})();
