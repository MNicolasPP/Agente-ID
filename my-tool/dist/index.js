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
Object.defineProperty(exports, "__esModule", { value: true });
exports.idProxyTool = void 0;
// --- Express endpoint para recibir JSON por POST ---
// --- IA-SPINE-TOOLS tool server ---
require("dotenv/config");
const tools_1 = require("@ai-spine/tools");
const fs = __importStar(require("fs"));
// Utilidad para convertir una imagen a base64 desde disco
function getImageBase64(imagePath) {
    try {
        return fs.readFileSync(imagePath, { encoding: 'base64' });
    }
    catch (err) {
        console.error('Error leyendo la imagen:', err);
        return '';
    }
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
                description: 'Image file path or base64 string. Can be a local path or a Buffer.',
            }),
            out_json: (0, tools_1.stringField)({
                required: true,
                description: 'Optional output JSON filename',
                default: 'ine_datos.json',
            }),
        },
        config: {
            python_url: {
                type: 'string',
                description: 'URL of the Python Identification Extractor Agent',
                required: false,
                default: 'http://127.0.0.1:3000'
            },
        },
    },
    async execute(input, config) {
        const url = `${config.python_url}/execute`;
        let imageBase64 = '';
        if (Buffer.isBuffer(input.image)) {
            imageBase64 = input.image.toString('base64');
        }
        else if (typeof input.image === 'string') {
            if (fs.existsSync(input.image)) {
                imageBase64 = getImageBase64(input.image);
            }
            else if (/^[A-Za-z0-9+/=]+$/.test(input.image.trim())) {
                // Ya es base64
                imageBase64 = input.image.trim();
            }
            else {
                throw new Error('Input validation failed: image debe ser una ruta válida, un Buffer o un string base64');
            }
        }
        else {
            throw new Error('Input validation failed: image debe ser una ruta válida, un Buffer o un string base64');
        }
        if (!imageBase64) {
            throw new Error('No se pudo convertir la imagen a base64');
        }
        const payload = {
            image_base64: imageBase64,
        };
        console.log('Payload enviado al servicio Python:', payload);
        if (input.out_json) {
            payload.out_json = input.out_json;
        }
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            return {
                status: 'error',
                success: false,
                output: null,
                error: {
                    code: 'server_error',
                    message: `Error from Python Identification Extractor Agent: ${response.statusText}`,
                    type: 'server_error',
                    httpStatusCode: response.status
                }
            };
        }
        const result = await response.json();
        return {
            status: result.error ? 'error' : 'success',
            success: !result.error,
            output: result,
            error: result.error
                ? {
                    code: 'execution_error',
                    message: result.error,
                    type: 'execution_error'
                }
                : undefined
        };
    }
});
// Iniciar el servidor solo si este archivo es el módulo principal
if (require.main === module) {
    exports.idProxyTool.start({
        port: process.env.PORT ? parseInt(process.env.PORT) : 4000,
        host: process.env.HOST || '0.0.0.0',
    });
}
//# sourceMappingURL=index.js.map