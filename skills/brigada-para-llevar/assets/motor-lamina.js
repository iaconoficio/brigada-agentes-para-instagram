// motor-lamina.js · La Brigada (IA con Oficio)
//
// El motor de dibujo de la Lámina de texto (herramientas/lamina-de-texto.html),
// copiado tal cual por herramientas/sincroniza_motor.py. No lo cambies a mano:
// cambia la Lámina y vuelve a ejecutar ese script.
//
// Necesita que quien lo use defina antes «estado» (como el de la Lámina) y
// «fotoImg» (la foto ya cargada, o null).

var FORMATOS = {
  feed:     { W: 1080, H: 1350, padX: 96,  padY: 110, max: 68, min: 30, nombre: "feed" },
  cuadrado: { W: 1080, H: 1080, padX: 96,  padY: 96,  max: 60, min: 28, nombre: "cuadrado" },
  story:    { W: 1080, H: 1920, padX: 96,  padY: 260, max: 72, min: 32, nombre: "story" }
};
var TEMAS = {
  blanco: { fondo: "#FFFFFF", texto: "#0F1419", sub: "#536471", inicial: "#CFD9DE", inicialTexto: "#0F1419" },
  negro:  { fondo: "#000000", texto: "#E7E9EA", sub: "#8B98A5", inicial: "#333639", inicialTexto: "#E7E9EA" }
};
var LETRAS = {
  sans:  '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif',
  serif: 'Georgia, "Iowan Old Style", "Times New Roman", serif',
  mono:  'ui-monospace, Menlo, Consolas, "Courier New", monospace'
};
var AZUL_VERIFICADO = "#1D9BF0";

var INVISIBLES = new RegExp("[" + [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD].map(function (c) { return String.fromCharCode(c); }).join("") + "]", "g");
var ESPACIOS_RAROS = new RegExp("[" + [0x00A0, 0x202F, 0x2009, 0x2007].map(function (c) { return String.fromCharCode(c); }).join("") + "]", "g");
function limpiarParaDibujar(t) { return t.replace(/\r\n?/g, "\n").replace(INVISIBLES, "").replace(ESPACIOS_RAROS, " "); }

// ---------- Dibujo ----------
function partirLineas(ctx, texto, ancho) {
  var lineas = [];
  texto.split("\n").forEach(function (parrafo) {
    if (parrafo.trim() === "") { lineas.push(null); return; }
    var palabras = parrafo.split(/ +/), actual = "";
    palabras.forEach(function (p) {
      var prueba = actual ? actual + " " + p : p;
      if (ctx.measureText(prueba).width <= ancho) { actual = prueba; return; }
      if (actual) lineas.push(actual);
      // Palabra más larga que la línea: se corta por letras.
      while (ctx.measureText(p).width > ancho && p.length > 1) {
        var i = p.length;
        while (i > 1 && ctx.measureText(p.slice(0, i)).width > ancho) i--;
        lineas.push(p.slice(0, i)); p = p.slice(i);
      }
      actual = p;
    });
    if (actual) lineas.push(actual);
  });
  while (lineas.length && lineas[lineas.length - 1] === null) lineas.pop();
  while (lineas.length && lineas[0] === null) lineas.shift();
  // Varias líneas en blanco seguidas cuentan como una.
  return lineas.filter(function (l, i) { return !(l === null && lineas[i - 1] === null); });
}
function altoTexto(lineas, tam) {
  var alto = 0;
  lineas.forEach(function (l) { alto += l === null ? tam * 0.6 : tam * 1.36; });
  return alto;
}
function ajustar(ctx, texto, fuente, ancho, altoMax, f) {
  // Busca la letra más grande con la que el texto cabe entero.
  var lo = f.min, hi = f.max, mejor = null;
  while (lo <= hi) {
    var mid = Math.floor((lo + hi) / 2);
    ctx.font = "400 " + mid + "px " + fuente;
    var lineas = partirLineas(ctx, texto, ancho);
    if (altoTexto(lineas, mid) <= altoMax) { mejor = { tam: mid, lineas: lineas }; lo = mid + 1; } else { hi = mid - 1; }
  }
  if (mejor) return { tam: mejor.tam, lineas: mejor.lineas, noCabe: false };
  ctx.font = "400 " + f.min + "px " + fuente;
  return { tam: f.min, lineas: partirLineas(ctx, texto, ancho), noCabe: true };
}
function recortar(ctx, t, ancho) {
  if (ctx.measureText(t).width <= ancho) return t;
  while (t.length > 1 && ctx.measureText(t + "...").width > ancho) t = t.slice(0, -1);
  return t + "...";
}
function iniciales(nombre) {
  var p = nombre.trim().split(/\s+/).filter(Boolean);
  return ((p[0] || "?")[0] + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase();
}
function dibujarAvatar(ctx, cx, cy, d, tema, fuente) {
  ctx.save();
  ctx.beginPath(); ctx.arc(cx, cy, d / 2, 0, Math.PI * 2); ctx.closePath(); ctx.clip();
  if (fotoImg) {
    var w = fotoImg.naturalWidth, h = fotoImg.naturalHeight;
    var s = Math.max(d / w, d / h) * estado.zoom, dw = w * s, dh = h * s;
    var dx = cx - dw / 2 - estado.moverX * (dw - d) / 2;
    var dy = cy - dh / 2 - estado.moverY * (dh - d) / 2;
    ctx.drawImage(fotoImg, dx, dy, dw, dh);
  } else {
    ctx.fillStyle = tema.inicial; ctx.fillRect(cx - d / 2, cy - d / 2, d, d);
    ctx.fillStyle = tema.inicialTexto; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.font = "700 " + Math.round(d * 0.38) + "px " + fuente;
    ctx.fillText(iniciales(estado.nombre || "?"), cx, cy + 2);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  }
  ctx.restore();
}
function dibujarVerificado(ctx, x, y, r) {
  ctx.save();
  ctx.fillStyle = AZUL_VERIFICADO; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = "#FFFFFF"; ctx.lineWidth = r * 0.2; ctx.lineCap = "round"; ctx.lineJoin = "round";
  ctx.beginPath(); ctx.moveTo(x - r * 0.42, y + r * 0.02); ctx.lineTo(x - r * 0.1, y + r * 0.34); ctx.lineTo(x + r * 0.46, y - r * 0.3); ctx.stroke();
  ctx.restore();
}
function temaActual() {
  if (estado.fondo === "propio") {
    var sub = mezclar(estado.colorTexto, estado.colorFondo, 0.62);
    return { fondo: estado.colorFondo, texto: estado.colorTexto, sub: sub, inicial: mezclar(estado.colorTexto, estado.colorFondo, 0.18), inicialTexto: estado.colorTexto };
  }
  return TEMAS[estado.fondo] || TEMAS.blanco;
}
function mezclar(a, b, t) {
  function rgb(h) { h = h.replace("#", ""); return [0, 2, 4].map(function (i) { return parseInt(h.slice(i, i + 2), 16); }); }
  var x = rgb(a), y = rgb(b);
  return "rgb(" + x.map(function (v, i) { return Math.round(v * t + y[i] * (1 - t)); }).join(",") + ")";
}
function dibujar(canvas, textoBruto, indice, total) {
  var f = FORMATOS[estado.formato] || FORMATOS.feed, tema = temaActual(), fuente = LETRAS[estado.letra] || LETRAS.sans;
  var texto = limpiarParaDibujar(textoBruto);
  canvas.width = f.W; canvas.height = f.H;
  var ctx = canvas.getContext("2d");
  ctx.fillStyle = tema.fondo; ctx.fillRect(0, 0, f.W, f.H);

  var d = 120, cabecera = d, hueco = 46, pieAlto = estado.numerar && total > 1 ? 60 : 0;
  var ancho = f.W - f.padX * 2;
  var altoMax = f.H - f.padY * 2 - cabecera - hueco - pieAlto;
  var m = ajustar(ctx, texto, fuente, ancho, altoMax, f);
  var bloque = cabecera + hueco + altoTexto(m.lineas, m.tam);
  var y0 = Math.max(f.padY, Math.round((f.H - pieAlto - bloque) / 2));

  // Cabecera: foto, nombre, verificado y usuario.
  var cx = f.padX + d / 2, cy = y0 + d / 2;
  dibujarAvatar(ctx, cx, cy, d, tema, fuente);
  var nx = f.padX + d + 28, maxNombre = ancho - d - 28 - (estado.verificado ? 52 : 0);
  ctx.fillStyle = tema.texto; ctx.textBaseline = "alphabetic"; ctx.font = "700 38px " + fuente;
  var nombre = recortar(ctx, (estado.nombre || "").trim() || "Tu nombre", maxNombre);
  ctx.fillText(nombre, nx, cy - 6);
  if (estado.verificado) dibujarVerificado(ctx, nx + ctx.measureText(nombre).width + 26, cy - 19, 17);
  ctx.fillStyle = tema.sub; ctx.font = "400 31px " + fuente;
  var usuario = (estado.usuario || "").trim().replace(/^@+/, "");
  ctx.fillText(recortar(ctx, "@" + (usuario || "tu_cuenta"), ancho - d - 28), nx, cy + 38);

  // Cuerpo del texto.
  ctx.fillStyle = tema.texto; ctx.font = "400 " + m.tam + "px " + fuente;
  var y = y0 + cabecera + hueco;
  m.lineas.forEach(function (l) {
    if (l === null) { y += m.tam * 0.6; return; }
    ctx.fillText(l, f.padX, y + m.tam * 1.02);
    y += m.tam * 1.36;
  });

  if (pieAlto) {
    ctx.fillStyle = tema.sub; ctx.font = "400 28px " + fuente; ctx.textAlign = "right";
    ctx.fillText((indice + 1) + "/" + total, f.W - f.padX, f.H - f.padY + 30);
    ctx.textAlign = "left";
  }
  return m;
}

// ZIP sin compresión (las JPG ya van comprimidas). Sin librerías de fuera.
var TABLA_CRC = (function () {
  var t = new Uint32Array(256);
  for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(d) { var c = 0xFFFFFFFF; for (var i = 0; i < d.length; i++) c = TABLA_CRC[(c ^ d[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function crearZip(archivos) {
  var ahora = new Date();
  var hora = (ahora.getHours() << 11) | (ahora.getMinutes() << 5) | (ahora.getSeconds() >> 1);
  var fecha = ((ahora.getFullYear() - 1980) << 9) | ((ahora.getMonth() + 1) << 5) | ahora.getDate();
  var enc = new TextEncoder(), partes = [], central = [], offset = 0;
  archivos.forEach(function (a) {
    var nombre = enc.encode(a.nombre), crc = crc32(a.datos), tam = a.datos.length;
    var cab = new DataView(new ArrayBuffer(30));
    cab.setUint32(0, 0x04034b50, true); cab.setUint16(4, 20, true); cab.setUint16(6, 0x0800, true); cab.setUint16(8, 0, true);
    cab.setUint16(10, hora, true); cab.setUint16(12, fecha, true); cab.setUint32(14, crc, true);
    cab.setUint32(18, tam, true); cab.setUint32(22, tam, true); cab.setUint16(26, nombre.length, true); cab.setUint16(28, 0, true);
    partes.push(new Uint8Array(cab.buffer), nombre, a.datos);
    var cd = new DataView(new ArrayBuffer(46));
    cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 20, true); cd.setUint16(6, 20, true); cd.setUint16(8, 0x0800, true); cd.setUint16(10, 0, true);
    cd.setUint16(12, hora, true); cd.setUint16(14, fecha, true); cd.setUint32(16, crc, true); cd.setUint32(20, tam, true); cd.setUint32(24, tam, true);
    cd.setUint16(28, nombre.length, true); cd.setUint16(30, 0, true); cd.setUint16(32, 0, true); cd.setUint16(34, 0, true); cd.setUint16(36, 0, true);
    cd.setUint32(38, 0, true); cd.setUint32(42, offset, true);
    central.push(new Uint8Array(cd.buffer), nombre);
    offset += 30 + nombre.length + tam;
  });
  var tamCentral = central.reduce(function (s, p) { return s + p.length; }, 0);
  var fin = new DataView(new ArrayBuffer(22));
  fin.setUint32(0, 0x06054b50, true); fin.setUint16(8, archivos.length, true); fin.setUint16(10, archivos.length, true);
  fin.setUint32(12, tamCentral, true); fin.setUint32(16, offset, true);
  return new Blob(partes.concat(central, [new Uint8Array(fin.buffer)]));
}
