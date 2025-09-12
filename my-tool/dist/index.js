"use strict";
/**
 * MyTool - Proxy tool that connects to Python Identification Extactor Agent
 *
 * This AI Spine tool provides basic text processing capabilities with configurable
 * parameters and robust input validation. It demonstrates the fundamental patterns
 * for building AI Spine compatible tools.
 *
 * Generated on 2025-09-11 using create-ai-spine-tool v1.0.0
 * Template: , Language: typescript
 *
 * @fileoverview Main tool implementation for my-tool
 * @author AI Spine Developer
 * @since 1.0.0
 */
Object.defineProperty(exports, "__esModule", { value: true });
// Load environment variables from .env file
require("dotenv/config");
const tools_1 = require("@ai-spine/tools");
/**
 * Main tool instance created using the AI Spine createTool factory.
 * This tool implements the universal AI Spine contract, making it compatible
 * with all AI Spine platforms and runtimes.
 */
const myToolTool = (0, tools_1.createTool)({
    /**
     * Tool metadata provides information about the tool's identity,
     * capabilities, and usage. This information is used for documentation
     * generation, tool discovery, and runtime introspection.
     */
    metadata: {
        name: 'my-tool',
        version: '1.0.0',
        description: 'Proxy tool that connects to Python Identification Extactor Agent',
        capabilities: ['text-processing'],
        author: 'Your Name',
        license: 'MIT',
    },
    /**
     * Schema definition describes the structure and validation rules for
     * both input data and configuration. The AI Spine framework uses this
     * schema to automatically validate inputs, generate documentation,
     * and provide type safety.
     */
    schema: {
        /**
         * Input schema defines the fields that users can provide when
         * executing this tool. Each field includes validation rules,
         * descriptions, and default values.
         */
        input: {
            message: (0, tools_1.stringField)({
                required: true,
                description: 'The message to process',
                minLength: 1,
                maxLength: 1000,
            }),
            count: (0, tools_1.numberField)({
                required: false,
                description: 'Number of times to repeat the message',
                min: 1,
                max: 10,
                default: 1,
            }),
            uppercase: (0, tools_1.booleanField)({
                required: false,
                description: 'Whether to convert message to uppercase',
                default: false,
            }),
        },
        /**
         * Configuration schema defines settings that can be provided via
         * environment variables or configuration files. These are typically
         * used for API keys, service endpoints, and operational parameters.
         */
        config: {
            api_key: (0, tools_1.apiKeyField)({
                required: false,
                description: 'Optional API key for external services',
            }),
            default_count: {
                type: 'number',
                required: false,
                description: 'Default count when not specified in input',
                default: 1,
            },
        },
    },
    /**
     * The execute function contains the main business logic of the tool.
     * It receives validated input data, configuration, and execution context,
     * then performs the requested operation and returns structured results.
     *
     * @param input - Validated input data matching the input schema
     * @param config - Configuration settings from environment/config files
     * @param context - Execution context with metadata and tracking information
     * @returns Promise resolving to structured execution results
     */
    async execute(input, config, context) {
        console.log(`Executing my-tool tool with execution ID: ${context.executionId}`);
        try {
            // Get the count from input or config default
            // This demonstrates how to merge input parameters with configuration defaults
            const count = input.count ?? config.default_count ?? 1;
            // Process the message according to the specified transformations
            let processedMessage = input.message;
            if (input.uppercase) {
                processedMessage = processedMessage.toUpperCase();
            }
            // Repeat the message according to the count parameter
            const result = Array(count).fill(processedMessage).join(' ');
            // Simulate some processing time (remove this in real implementations)
            await new Promise(resolve => setTimeout(resolve, 100));
            // Return structured results following AI Spine conventions
            // The response includes the processed data, metadata, and execution information
            return {
                status: 'success',
                data: {
                    processed_message: result,
                    original_message: input.message,
                    transformations: {
                        uppercase: input.uppercase || false,
                        count: count,
                    },
                    metadata: {
                        execution_id: context.executionId,
                        timestamp: context.timestamp.toISOString(),
                        tool_version: '1.0.0',
                    },
                },
            };
        }
        catch (error) {
            console.error('Error processing message:', error);
            // Always provide meaningful error messages to help users troubleshoot issues
            throw new Error(`Failed to process message: ${error instanceof Error ? error.message : String(error)}`);
        }
    },
});
/**
 * Main entry point that starts the tool server with configurable options.
 * The server exposes REST endpoints that comply with the AI Spine universal contract:
 * - GET /health - Health check and tool metadata
 * - POST /execute - Execute the tool with input data
 * - GET /schema - Tool schema and documentation
 *
 * Configuration is loaded from environment variables, allowing for flexible
 * deployment across different environments.
 */
async function main() {
    try {
        await myToolTool.start({
            // Server configuration from environment variables with sensible defaults
            port: process.env.PORT ? parseInt(process.env.PORT) : 3000,
            host: process.env.HOST || '0.0.0.0',
            // Development features for easier debugging and testing
            development: {
                requestLogging: process.env.NODE_ENV === 'development'
            },
            // Security configuration for production deployments
            security: {
                requireAuth: process.env.API_KEY_AUTH === 'true',
                ...(process.env.VALID_API_KEYS && { apiKeys: process.env.VALID_API_KEYS.split(',') }),
            },
        });
        console.log(`🚀 MyTool tool server started successfully`);
        console.log(`📡 Listening on port ${process.env.PORT || 3000}`);
        console.log(`🔗 Health check: http://localhost:${process.env.PORT || 3000}/health`);
    }
    catch (error) {
        console.error('Failed to start tool server:', error);
        process.exit(1);
    }
}
/**
 * Graceful shutdown handlers ensure the tool server stops cleanly when
 * receiving termination signals. This is important for:
 * - Completing ongoing requests
 * - Cleaning up resources
 * - Proper logging and monitoring
 * - Container orchestration compatibility
 */
// Handle SIGINT (Ctrl+C) for graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n🔄 Received SIGINT, shutting down gracefully...');
    await myToolTool.stop();
    process.exit(0);
});
// Handle SIGTERM (container/process manager termination) for graceful shutdown
process.on('SIGTERM', async () => {
    console.log('🔄 Received SIGTERM, shutting down gracefully...');
    await myToolTool.stop();
    process.exit(0);
});
// Start the server if this file is run directly (not when imported as a module)
if (require.main === module) {
    main();
}
/**
 * Export the tool instance for use in tests, other modules, or programmatic usage.
 * This allows the tool to be imported and used without starting the HTTP server.
 */
exports.default = myToolTool;
//# sourceMappingURL=index.js.map