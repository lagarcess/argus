export default {
  client: 'axios',
  input: 'http://127.0.0.1:8000/openapi.json',
  output: {
    format: 'prettier',
    lint: 'eslint',
    path: './lib/generated',
  },
};
