# Use Node.js LTS (Lightweight Alpine)
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies (production only)
RUN npm ci --only=production

# Copy the rest of the backend code
COPY . .

# Ensure the uploads directory exists
RUN mkdir -p uploads

# Expose the API port (Default 5000)
EXPOSE 5000

# Start the server
CMD ["npm", "start"]
