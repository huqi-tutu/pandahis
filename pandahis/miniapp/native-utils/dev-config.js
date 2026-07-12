"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEV_API_PORT = exports.DEV_LAN_HOST = void 0;
/**
 * 本地开发联调配置
 * 真机预览时手机无法访问 localhost，需填写开发机局域网 IP。
 * Mac 终端查询: ipconfig getifaddr en0
 */
exports.DEV_LAN_HOST = '192.168.1.18';
exports.DEV_API_PORT = 8080;
