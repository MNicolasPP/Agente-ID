// --- Express endpoint para recibir JSON por POST ---
// --- IA-SPINE-TOOLS tool server ---
import 'dotenv/config';
import { createTool, stringField } from '@ai-spine/tools';
import * as fs from 'fs';

type ImageInput = string | Buffer;

interface ProxyInput {
  image: ImageInput; // buffer o ruta de imagen
  out_json?: string; // nombre de archivo opcional
}

interface ProxyConfig {
  python_url?: string;
}


// Utilidad para convertir una imagen a base64 desde disco
function getImageBase64(imagePath: string): string {
  try {
    return fs.readFileSync(imagePath, { encoding: 'base64' });
  } catch (err) {
    console.error('Error leyendo la imagen:', err);
    return '';
  }
}

export const idProxyTool = createTool<ProxyInput, ProxyConfig>({
  metadata:
  {
    name: 'identification-proxy-tool',
    description: 'Proxy tool that connects to Python Identification Extractor Agent',
    version: '1.0.0',
    capabilities: ['id-extraction'],
    author: 'Your Name',
    license: 'MIT',

  },
  schema:{
    input:{
      image: stringField({
        required: true,
        description: 'Image file path or base64 string. Can be a local path or a Buffer.',
      }),
      out_json: stringField({
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
    } else if (typeof input.image === 'string') {
      if (fs.existsSync(input.image)) {
        imageBase64 = getImageBase64(input.image);
      } else if (/^[A-Za-z0-9+/=]+$/.test(input.image.trim())) {
        // Ya es base64
        imageBase64 = input.image.trim();
      } else {
        throw new Error('Input validation failed: image debe ser una ruta válida, un Buffer o un string base64');
      }
    } else {
      throw new Error('Input validation failed: image debe ser una ruta válida, un Buffer o un string base64');
    }
    if (!imageBase64) {
      throw new Error('No se pudo convertir la imagen a base64');
    }
    const payload: Record<string, any> = {
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

    const result = await response.json() as { error?: string; [key: string]: any };
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
if (require.main === module){
  idProxyTool.start({
    port: process.env.PORT ? parseInt(process.env.PORT) : 4000,
    host: process.env.HOST || '0.0.0.0',
  });

}
