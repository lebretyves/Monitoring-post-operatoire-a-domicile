FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY vite.config.ts .
COPY src ./src

RUN printf '%s\n' \
  '<!doctype html>' \
  '<html lang="en">' \
  '  <head>' \
  '    <meta charset="UTF-8" />' \
  '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />' \
  '    <title>Postop Monitoring</title>' \
  '  </head>' \
  '  <body>' \
  '    <div id="root"></div>' \
  '    <script type="module" src="/src/main.tsx"></script>' \
  '  </body>' \
  '</html>' > index.html

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
