FROM node:20

WORKDIR /app
COPY ./my-tool /app

RUN npm install
RUN npm run build

EXPOSE 4000
CMD ["npm", "start"]