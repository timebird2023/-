export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-csrf-token, User-Agent, Connection, Accept-Encoding, Cache-Control, Cookie');
    
    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }
    
    try {
        const { url, method = 'GET', headers = {}, body } = req.body;
        
        if (!url) {
            return res.status(400).json({ error: 'URL is required' });
        }
        
        const fetchOptions = {
            method: method,
            headers: {
                'User-Agent': headers['User-Agent'] || 'Djezzy/2.7.5',
                'Connection': headers['Connection'] || 'Keep-Alive',
                'Accept-Encoding': headers['Accept-Encoding'] || 'gzip',
                ...headers
            }
        };
        
        if (body && method !== 'GET') {
            fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
        }
        
        const response = await fetch(url, fetchOptions);
        const contentType = response.headers.get('content-type');
        
        let data;
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            data = await response.text();
        }
        
        return res.status(response.status).json({
            success: response.ok,
            status: response.status,
            data: data
        });
        
    } catch (error) {
        return res.status(500).json({
            success: false,
            error: error.message
        });
    }
}
