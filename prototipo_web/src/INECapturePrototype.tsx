import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Camera,
  CameraOff,
  Download,
  RefreshCw,
  FlipHorizontal,
  ScanFace,
  Aperture,
} from "lucide-react";
import { motion } from "framer-motion";

type Rot = 0 | 90 | 180 | 270;

export default function INECapturePrototype() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [mirrored, setMirrored] = useState<boolean>(false);
  const [rotation, setRotation] = useState<Rot>(0);
  const [captureUrl, setCaptureUrl] = useState<string | null>(null);

  // Calidad JPG fija (sin slider)
  const [snapQuality] = useState<number>(0.95);

  // Relación ID-1 ≈ 1.586
  const ID_RATIO = 85.6 / 53.98;

  // Enumerar cámaras (pide permiso una vez para obtener labels)
  useEffect(() => {
    async function initDevices() {
      try {
        await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        const list = await navigator.mediaDevices.enumerateDevices();
        const cams = list.filter((d) => d.kind === "videoinput");
        setDevices(cams);
        if (cams.length && !deviceId) {
          const continuity = cams.find((c) =>
            /iphone|continuity|ios/i.test(c.label)
          );
          setDeviceId((continuity || cams[0]).deviceId);
        }
      } catch (e) {
        console.error(e);
        alert("No se pudo acceder a la cámara. Revisa permisos del navegador.");
      }
    }
    initDevices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startStream = async () => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      const constraints: MediaStreamConstraints = {
        video: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          facingMode: "environment",
        },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (!videoRef.current) return;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      streamRef.current = stream;
      setIsStreaming(true);
    } catch (e) {
      console.error(e);
      alert("No se pudo iniciar el stream de la cámara seleccionada.");
    }
  };

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  };

  // Nombre de archivo para descarga
  const downloadName = useMemo(() => {
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    return `INE-capture-${ts}.jpg`;
  }, [captureUrl]);

  // Captura exacta del área del marco
  const handleCapture = () => {
    if (!videoRef.current || !overlayRef.current) return;
    const video = videoRef.current;

    const vw = video.clientWidth;
    const vh = video.clientHeight;
    const vW = video.videoWidth || 1920;
    const vH = video.videoHeight || 1080;

    const ob = overlayRef.current.getBoundingClientRect();
    const vb = video.getBoundingClientRect();

    const relLeft = ob.left - vb.left;
    const relTop = ob.top - vb.top;

    const scaleX = vW / vw;
    const scaleY = vH / vh;

    const sx = Math.max(0, Math.round(relLeft * scaleX));
    const sy = Math.max(0, Math.round(relTop * scaleY));
    const sw = Math.min(vW - sx, Math.round(ob.width * scaleX));
    const sh = Math.min(vH - sy, Math.round(ob.height * scaleY));

    const canvas = canvasRef.current || document.createElement("canvas");
    canvas.width = sw;
    canvas.height = sh;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.save();
    if (mirrored || rotation !== 0) {
      const temp = document.createElement("canvas");
      temp.width = vW;
      temp.height = vH;
      const tctx = temp.getContext("2d")!;
      tctx.save();
      tctx.translate(vW / 2, vH / 2);
      if (rotation !== 0) tctx.rotate((rotation * Math.PI) / 180);
      const scaleMirror = mirrored ? -1 : 1;
      tctx.scale(scaleMirror, 1);
      tctx.drawImage(video, -vW / 2, -vH / 2, vW, vH);
      tctx.restore();

      const tdata = tctx.getImageData(sx, sy, sw, sh);
      ctx.putImageData(tdata, 0, 0);
    } else {
      ctx.drawImage(video, sx, sy, sw, sh, 0, 0, sw, sh);
    }
    ctx.restore();

    const url = canvas.toDataURL("image/jpeg", snapQuality);
    setCaptureUrl(url);
  };

  const toggleMirror = () => setMirrored((m) => !m);
  const rotate = () => setRotation(((rotation + 90) % 360) as Rot);

  // Estilos de botones
  const btnBase: React.CSSProperties = {
    padding: "8px 12px",
    borderRadius: 10,
    border: "1px solid #e5e7eb",
    display: "inline-flex",
    alignItems: "center",
    textDecoration: "none",
    cursor: "pointer",
  };
  const btnPrimary: React.CSSProperties = {
    ...btnBase,
    background: "#10b981",
    color: "#fff",
    border: "none",
  };
  const btnDanger: React.CSSProperties = {
    ...btnBase,
    background: "#e11d48",
    color: "#fff",
    border: "none",
  };
  const btnIndigo: React.CSSProperties = {
    ...btnBase,
    background: "#4f46e5",
    color: "#fff",
    border: "none",
  };
  const btnGhost: React.CSSProperties = {
    ...btnBase,
    background: "#fff",
    color: "#111",
  };

  return (
    <div style={{ minHeight: "100vh", background: "#fff", color: "#111" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
        {/* Header */}
        <header
          style={{
            display: "flex",
            gap: 12,
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <ScanFace size={22} />
            <h1 style={{ fontSize: 22, fontWeight: 600 }}>ID Captura</h1>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={toggleMirror} style={btnGhost}>
              <FlipHorizontal size={16} style={{ marginRight: 6 }} /> Espejo{" "}
              {mirrored ? "ON" : "OFF"}
            </button>
            <button onClick={rotate} style={btnGhost}>
              <RefreshCw size={16} style={{ marginRight: 6 }} /> Rotar {rotation}
              °
            </button>
          </div>
        </header>

        {/* Controles */}
        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "flex-end",
            flexWrap: "wrap",
            marginBottom: 12,
          }}
        >
          <div style={{ flex: 1, minWidth: 280 }}>
            <label style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
              Cámara
            </label>
            <select
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              style={{ width: "100%", padding: "8px 10px" }}
            >
              {devices.map((d) => (
                <option key={d.deviceId} value={d.deviceId}>
                  {d.label || `Cámara ${d.deviceId.slice(0, 6)}...`}
                </option>
              ))}
            </select>
            <div style={{ fontSize: 12, opacity: 0.7, marginTop: 4 }}>
              Tip: en macOS puedes elegir <em>Continuity Camera</em> para usar el
              iPhone.
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {!isStreaming ? (
              <button onClick={startStream} style={btnPrimary}>
                <Camera size={16} style={{ marginRight: 6 }} /> Iniciar
              </button>
            ) : (
              <button onClick={stopStream} style={btnDanger}>
                <CameraOff size={16} style={{ marginRight: 6 }} /> Detener
              </button>
            )}
            <button
              onClick={handleCapture}
              disabled={!isStreaming}
              style={btnIndigo}
            >
              <Aperture size={16} style={{ marginRight: 6 }} /> Capturar
            </button>
          </div>
        </div>

        {/* Área en vivo */}
        <div
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              position: "relative",
              aspectRatio: "16 / 9",
              background: "#fafafa",
            }}
          >
            <motion.video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                transform: `rotate(${rotation}deg) ${
                  mirrored ? "scaleX(-1)" : ""
                }`,
              }}
            />

            {/* Marco centrado ID-1 */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                pointerEvents: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                ref={overlayRef}
                style={{
                  position: "relative",
                  width: "min(75%, 900px)",
                  aspectRatio: `${ID_RATIO}`,
                }}
              >
                {/* sombreado exterior */}
                <div style={{ position: "absolute", inset: -24 }}>
                  <svg
                    width="100%"
                    height="100%"
                    viewBox="0 0 100 100"
                    preserveAspectRatio="none"
                  >
                    <defs>
                      <mask id="hole">
                        <rect
                          x="0"
                          y="0"
                          width="100"
                          height="100"
                          fill="white"
                        />
                        {/* recorte central */}
                        <rect x="10" y="25" width="80" height="50" fill="black" />
                      </mask>
                    </defs>
                    <rect
                      x="0"
                      y="0"
                      width="100"
                      height="100"
                      mask="url(#hole)"
                      fill="rgba(0,0,0,0.45)"
                    />
                  </svg>
                </div>

                {/* borde del marco */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    border: "4px solid #10b981",
                    borderRadius: 12,
                  }}
                />

                {/* texto de ayuda */}
                <div
                  style={{
                    position: "absolute",
                    left: "50%",
                    transform: "translateX(-50%)",
                    bottom: -28,
                    fontSize: 12,
                    opacity: 0.85,
                    textAlign: "center",
                  }}
                >
                  Coloca la INE dentro del marco. Evita bordes visibles.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Canvas oculto para la captura */}
        <canvas ref={canvasRef} style={{ display: "none" }} />

        {/* Resultado */}
        <div
          style={{
            marginTop: 24,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
          }}
        >
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              Resultado
            </h2>
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                minHeight: 220,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "#f8fafc",
              }}
            >
              {captureUrl ? (
                <img
                  src={captureUrl}
                  alt="Captura"
                  style={{ maxHeight: 360, objectFit: "contain", borderRadius: 6 }}
                />
              ) : (
                <p style={{ fontSize: 14, opacity: 0.7 }}>
                  Aún no hay captura. Presiona <strong>Capturar</strong>.
                </p>
              )}
            </div>
            {captureUrl && (
              <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <a href={captureUrl} download={downloadName} style={btnPrimary}>
                  <Download size={16} style={{ marginRight: 6 }} /> Descargar JPG
                </a>
                <button onClick={() => setCaptureUrl(null)} style={btnGhost}>
                  <RefreshCw size={16} style={{ marginRight: 6 }} /> Limpiar
                </button>
              </div>
            )}
          </div>

          <div>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              Notas
            </h2>
            <ul style={{ fontSize: 14, opacity: 0.9, paddingLeft: 18 }}>
              <li>
                El marco respeta la relación ID-1 (~1.586:1) y la captura recorta
                exactamente esa área.
              </li>
              <li>
                Selecciona la cámara (Continuity Camera del iPhone funciona en
                macOS).
              </li>
              <li>
                Usa <em>Espejo</em> o <em>Rotar</em> si la orientación no coincide.
              </li>
              <li>
                El JPG queda listo para pasarlo a tu función{" "}
                <code>procesar_ine()</code>.
              </li>
            </ul>
          </div>
        </div>

        <footer
          style={{ marginTop: 28, fontSize: 12, opacity: 0.6, textAlign: "center" }}
        >
          Prototipo local sin backend.
        </footer>
      </div>
    </div>
  );
}
