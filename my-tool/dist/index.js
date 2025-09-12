"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.idProxyTool = void 0;
// --- IA-SPINE-TOOLS tool server ---
require("dotenv/config");
const tools_1 = require("@ai-spine/tools");
const fs = __importStar(require("fs"));
const axios_1 = __importDefault(require("axios"));
// Convierte imagen en disco a base64
function getImageBase64(imagePath) {
    try {
        return fs.readFileSync(imagePath, { encoding: 'base64' });
    }
    catch (err) {
        console.error('Error leyendo la imagen:', err);
        return '';
    }
}
// Quita prefijo data URI si viene así
function stripDataUriPrefix(s) {
    const idx = s.indexOf('base64,');
    return idx >= 0 ? s.slice(idx + 'base64,'.length) : s;
}
// Heurística simple para detectar base64
function isLikelyBase64(s) {
    const clean = s.replace(/\s+/g, '');
    return /^[A-Za-z0-9+/=]+$/.test(clean) && clean.length % 4 === 0;
}
exports.idProxyTool = (0, tools_1.createTool)({
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
            image: (0, tools_1.stringField)({
                required: true,
                description: 'Image file path or base64 string. Can be a local path, a data URI, or a Buffer (as base64).',
            }),
            out_json: (0, tools_1.stringField)({
                required: false, // <- ya tiene default
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
        }
        else if (typeof input.image === 'string') {
            const str = input.image.trim();
            if (fs.existsSync(str)) {
                // Es ruta en disco
                imageBase64 = getImageBase64(str);
            }
            else {
                // Puede venir como data URI o base64 directo
                const maybeB64 = stripDataUriPrefix(str).replace(/\s+/g, '');
                if (isLikelyBase64(maybeB64)) {
                    imageBase64 = maybeB64;
                }
                else {
                    throw new Error('Input validation failed: `image` debe ser una ruta válida, un Buffer o un string base64 (data URI permitido).');
                }
            }
        }
        else {
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
            const resp = await axios_1.default.post(url, payload, {
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
                output: result, // aquí cambie para que regrese el JSON
            };
        }
        catch (err) {
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
    exports.idProxyTool.start({
        port: process.env.PORT ? parseInt(process.env.PORT, 10) : 4000,
        host: process.env.HOST || '0.0.0.0',
    });
}
//# sourceMappingURL=index.js.map