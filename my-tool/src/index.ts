// --- IA-SPINE-TOOLS tool server ---
import 'dotenv/config';
import { createTool, stringField } from '@ai-spine/tools';
import * as fs from 'fs';
import axios from 'axios';

type ImageInput = string | Buffer;

interface ProxyInput {
  image: ImageInput;   // ruta de archivo, data URI/base64 o Buffer
  out_json?: string;   // nombre del archivo de salida (opcional)
}

interface ProxyConfig {
  python_url?: string; // URL del servicio Python; por defecto http://127.0.0.1:3000
}

// Convierte imagen en disco a base64
function getImageBase64(imagePath: string): string {
  try {
    return fs.readFileSync(imagePath, { encoding: 'base64' });
  } catch (err) {
    console.error('Error leyendo la imagen:', err);
    return '';
  }
}

// Quita prefijo data URI si viene así
function stripDataUriPrefix(s: string): string {
  const idx = s.indexOf('base64,');
  return idx >= 0 ? s.slice(idx + 'base64,'.length) : s;
}

// Heurística simple para detectar base64
function isLikelyBase64(s: string): boolean {
  const clean = s.replace(/\s+/g, '');
  return /^[A-Za-z0-9+/=]+$/.test(clean) && clean.length % 4 === 0;
}

export const idProxyTool = createTool<ProxyInput, ProxyConfig>({
  metadata: {
    name: 'identification-proxy-tool',
    description: 'Proxy tool that connects to Python Identification Extractor Agent',
    version: '1.0.0',
    capabilities: ['id-extraction'],
    author: 'Your Name',
    license: 'MIT',
  },

  schema: {
    input: {
      image: stringField({
        required: true,
        description:
          'Image file path or base64 string. Can be a local path, a data URI, or a Buffer (as base64).',
      }),
      out_json: stringField({
        required: false,                 // <- ya tiene default
        description: 'Optional output JSON filename',
        default: 'ine_datos.json',
      }),
    },
    config: {
      python_url: {
        type: 'string',
        description: 'URL of the Python Identification Extractor Agent',
        required: false,
        default: 'http://127.0.0.1:3000',
      },
    },
  },

  async execute(input, config) {
    // Normaliza URL y endpoint
    const pythonBase = (config?.python_url ?? 'http://127.0.0.1:3000').replace(/\/+$/, '');
    const url = `${pythonBase}/execute`;

    // Normaliza imagen -> base64
    let imageBase64 = '';
    if (Buffer.isBuffer(input.image)) {
      imageBase64 = input.image.toString('base64');
    } else if (typeof input.image === 'string') {
      const str = input.image.trim();

      if (fs.existsSync(str)) {
        // Es ruta en disco
        imageBase64 = getImageBase64(str);
      } else {
        // Puede venir como data URI o base64 directo
        const maybeB64 = stripDataUriPrefix(str).replace(/\s+/g, '');
        if (isLikelyBase64(maybeB64)) {
          imageBase64 = maybeB64;
        } else {
          throw new Error(
            'Input validation failed: `image` debe ser una ruta válida, un Buffer o un string base64 (data URI permitido).'
          );
        }
      }
    } else {
      throw new Error('Input validation failed: tipo de `image` no soportado.');
    }

    if (!imageBase64) {
      throw new Error('No se pudo convertir la imagen a base64.');
    }

    const outJson = input.out_json || 'ine_datos.json';
    const payload = { image_base64: imageBase64, out_json: outJson };

    // Logs útiles
    console.log('POST ->', url);
    console.log('image_base64 length:', imageBase64.length);
    console.log('out_json:', outJson);

    try {
      const resp = await axios.post(url, payload, {
        headers: { 'Content-Type': 'application/json' },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: 120_000,
      });

      const result = resp.data;
      console.log('PY result:', result);

      return {
        status: 'success',
        success: true,
        output: result,        // aquí cambie para que regrese el JSON
      };

    } catch (err: any) {
      console.error('PY CALL FAILED:', {
        msg: err?.message,
        code: err?.code,
        status: err?.response?.status,
        data: err?.response?.data,
        url,
      });

      return {
        status: 'error',
        success: false,
        output: null,
        error: {
          code: err?.code || 'PY_BACKEND_ERROR',
          message: err?.message || 'Python call failed',
          type: 'server_error',
          httpStatusCode: err?.response?.status,
          details: err?.response?.data,
        },
      };
    }
  },
});

// Iniciar el servidor solo si este archivo es el módulo principal
if (require.main === module) {
  idProxyTool.start({
    port: process.env.PORT ? parseInt(process.env.PORT, 10) : 4000,
    host: process.env.HOST || '0.0.0.0',
  });
}
