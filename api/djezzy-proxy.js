export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', '*');
    res.setHeader('Access-Control-Max-Age', '86400');
    
    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }
    
    try {
        let requestData;
        
        if (req.method === 'POST') {
            requestData = req.body;
        } else if (req.method === 'GET') {
            requestData = req.query;
        } else {
            return res.status(405).json({ error: 'Method not allowed' });
        }
        
        const { url, method = 'GET', headers = {}, body } = requestData;
        
        if (!url) {
            return res.status(400).json({ 
                success: false,
                error: 'URL is required',
                received: requestData 
            });
        }
        
        const fetchOptions = {
            method: method.toUpperCase(),
            headers: {
                'User-Agent': headers['User-Agent'] || 'Djezzy/2.7.5',
                'Connection': headers['Connection'] || 'Keep-Alive',
                'Accept-Encoding': headers['Accept-Encoding'] || 'gzip',
                'Content-Type': headers['Content-Type'] || 'application/json',
                ...headers
            }
        };
        
        if (body && method.toUpperCase() !== 'GET' && method.toUpperCase() !== 'HEAD') {
            if (typeof body === 'object' && headers['Content-Type']?.includes('application/x-www-form-urlencoded')) {
                fetchOptions.body = body;
            } else if (typeof body === 'string') {
                fetchOptions.body = body;
            } else {
                fetchOptions.body = JSON.stringify(body);
            }
        }
        
        const response = await fetch(url, fetchOptions);
        const contentType = response.headers.get('content-type');
        
        let data;
        if (contentType && contentType.includes('application/json')) {
            try {
                data = await response.json();
            } catch (e) {
                data = await response.text();
            }
        } else {
            data = await response.text();
        }
        
        return res.status(200).json({
            success: response.ok,
            status: response.status,
            statusText: response.statusText,
            data: data
        });
        
    } catch (error) {
        console.error('Proxy error:', error);
        return res.status(500).json({
            success: false,
            error: error.message,
            stack: error.stack
        });
    }
}
