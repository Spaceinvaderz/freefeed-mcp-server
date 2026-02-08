#!/bin/bash
# generate_cert.sh - Generate a self-signed SSL certificate

echo "🔐 Generating a self-signed SSL certificate for FreeFeed API"
echo ""

# Create a directory for certificates
mkdir -p certs
cd certs

# Generate private key and certificate
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout key.pem \
  -out cert.pem \
  -days 365 \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=FreeFeed/OU=MCP/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"

echo ""
echo "✅ Certificate created successfully!"
echo ""
echo "📁 Files saved in certs/ directory:"
echo "   - cert.pem (public certificate)"
echo "   - key.pem (private key)"
echo ""
echo "⚠️  IMPORTANT for Claude Desktop:"
echo ""
echo "macOS:"
echo "  1. Open Keychain Access"
echo "  2. Drag cert.pem into the 'System' keychain"
echo "  3. Double-click the certificate"
echo "  4. Expand 'Trust' -> select 'Always Trust'"
echo ""
echo "Windows:"
echo "  1. Open cert.pem"
echo "  2. Install Certificate -> Local Machine"
echo "  3. Place in 'Trusted Root Certification Authorities'"
echo ""
echo "Linux:"
echo "  sudo cp cert.pem /usr/local/share/ca-certificates/freefeed.crt"
echo "  sudo update-ca-certificates"
echo ""
echo "🚀 Now run the API server with HTTPS:"
echo "   python -m freefeed_mcp_server.api --ssl"
echo ""
