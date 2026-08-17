# Store CMS Frontend Integration Guide
## Building Dynamic Customer-Facing Store Pages

This guide shows how to integrate the new Store CMS with your frontend store pages.

---

## 📡 Available API Endpoints

### Product Search & Discovery

#### 1. Search Products
```
GET /store/api/products/search?q=laptop&category=Electronics&sort=new&page=1&per_page=12
```
**Query Parameters:**
- `q`: Search query (searches name, description, tags, brand)
- `category`: Filter by category
- `subcategory`: Filter by subcategory  
- `brand`: Filter by brand
- `sort`: new | popular | price_low | price_high | rating
- `page`: Pagination (default: 1)
- `per_page`: Items per page (default: 12)

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": 1,
      "name": "Laptop Model X",
      "slug": "laptop-model-x",
      "price": 50000,
      "discount_price": 45000,
      "image_url": "/uploads/products/...",
      "rating": 4.5,
      "brand": "TechBrand",
      "category": "Electronics",
      "is_featured": true,
      "is_trending": false,
      "is_new_arrival": true,
      "stock": 12,
      "in_stock": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 12,
    "total": 45,
    "pages": 4
  }
}
```

#### 2. Get Product Details
```
GET /store/api/products/123
```

**Response:**
```json
{
  "success": true,
  "product": {
    "id": 123,
    "name": "Product Name",
    "slug": "product-slug",
    "description": "...",
    "short_description": "...",
    "price": 5000,
    "discount_price": 4500,
    "image_url": "/uploads/products/...",
    "gallery": [
      {"id": 1, "url": "/uploads/products/...", "order": 0},
      {"id": 2, "url": "/uploads/products/...", "order": 1}
    ],
    "rating": 4.5,
    "reviews_count": 12,
    "brand": "BrandName",
    "category": "Category",
    "subcategory": "SubCategory",
    "tags": ["tag1", "tag2"],
    "sku": "SO-ABC12345",
    "stock": 50,
    "in_stock": true,
    "low_stock": false,
    "specifications": [
      {"key": "Color", "value": "Black"},
      {"key": "Size", "value": "Medium"}
    ],
    "features": [
      "Feature 1",
      "Feature 2"
    ],
    "warranty": "1 Year",
    "video_url": "https://youtube.com/...",
    "gst_percent": 18,
    "is_featured": true,
    "is_trending": true,
    "is_new_arrival": false,
    "seo": {
      "title": "SEO Title",
      "description": "SEO Description",
      "keywords": "keyword1, keyword2",
      "canonical_url": "https://...",
      "og_image": "/uploads/..."
    }
  },
  "reviews": [
    {
      "id": 1,
      "user": "john_doe",
      "rating": 5,
      "text": "Excellent product!",
      "created_at": "2024-05-10T10:30:00"
    }
  ]
}
```

#### 3. Get Featured Products
```
GET /store/api/products/featured?limit=8
```

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "id": 1,
      "name": "Featured Product",
      "slug": "featured-product",
      "price": 5000,
      "discount_price": 4500,
      "image_url": "/uploads/products/...",
      "rating": 4.8
    }
  ]
}
```

#### 4. Get Categories
```
GET /store/api/categories
```

**Response:**
```json
{
  "success": true,
  "categories": [
    {
      "id": 1,
      "name": "Electronics",
      "slug": "electronics",
      "icon_url": "/uploads/products/...",
      "banner_url": "/uploads/products/...",
      "product_count": 45
    }
  ]
}
```

#### 5. Get Filter Options
```
GET /store/api/filters?category=Electronics
```

**Response:**
```json
{
  "success": true,
  "filters": {
    "brands": ["TechBrand", "OtherBrand"],
    "price_ranges": [
      {"label": "Under ₹1000", "min": 0, "max": 1000},
      {"label": "₹1000 - ₹5000", "min": 1000, "max": 5000}
    ],
    "min_price": 1000,
    "max_price": 50000
  }
}
```

#### 6. Get Related Products
```
GET /store/api/products/related/123?limit=4
```

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "id": 124,
      "name": "Related Product",
      "slug": "related-product",
      "price": 5000,
      "discount_price": 4500,
      "image_url": "/uploads/products/...",
      "rating": 4.5
    }
  ]
}
```

---

## 🎨 Frontend Template Examples

### Store Homepage - Featured Products Section
```html
<!-- Using JavaScript Fetch API -->
<script>
  async function loadFeaturedProducts() {
    const response = await fetch('/store/api/products/featured?limit=8');
    const data = await response.json();
    
    if (data.success) {
      const container = document.getElementById('featured-products');
      data.products.forEach(product => {
        container.innerHTML += `
          <div class="product-card">
            <img src="${product.image_url}" alt="${product.name}">
            <h3>${product.name}</h3>
            <div class="rating">⭐ ${product.rating}</div>
            <div class="price">
              <span class="original">₹${product.price}</span>
              <span class="discount">₹${product.discount_price}</span>
            </div>
            <a href="/store/product/${product.slug}" class="btn-view">View Details</a>
          </div>
        `;
      });
    }
  }
  
  document.addEventListener('DOMContentLoaded', loadFeaturedProducts);
</script>

<div id="featured-products" class="products-grid"></div>
```

### Product Search & Filter Page
```html
<!-- Search form with filters -->
<form id="search-form" class="search-filters">
  <input type="text" name="q" placeholder="Search products...">
  
  <select name="category" id="category-filter">
    <option value="">All Categories</option>
  </select>
  
  <select name="brand" id="brand-filter">
    <option value="">All Brands</option>
  </select>
  
  <select name="sort">
    <option value="new">Newest</option>
    <option value="popular">Most Popular</option>
    <option value="price_low">Price: Low to High</option>
    <option value="price_high">Price: High to Low</option>
    <option value="rating">Highest Rated</option>
  </select>
  
  <button type="submit">Search</button>
</form>

<script>
  // Load categories on page load
  async function loadCategories() {
    const response = await fetch('/store/api/categories');
    const data = await response.json();
    
    const categorySelect = document.getElementById('category-filter');
    data.categories.forEach(cat => {
      const option = document.createElement('option');
      option.value = cat.slug;
      option.textContent = `${cat.name} (${cat.product_count})`;
      categorySelect.appendChild(option);
    });
  }
  
  // Handle search form submission
  document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const params = new URLSearchParams(formData);
    const response = await fetch(`/store/api/products/search?${params}`);
    const data = await response.json();
    
    displaySearchResults(data.items);
  });
  
  document.addEventListener('DOMContentLoaded', loadCategories);
</script>
```

### Product Detail Page
```html
<!-- /store/product/<slug> -->
<script>
  async function loadProductDetail() {
    const productId = document.getElementById('product-id').value;
    
    const response = await fetch(`/store/api/products/${productId}`);
    const data = await response.json();
    
    if (data.success) {
      const product = data.product;
      
      // Display product info
      document.getElementById('product-name').textContent = product.name;
      document.getElementById('product-rating').textContent = `⭐ ${product.rating}`;
      document.getElementById('product-price').textContent = `₹${product.price}`;
      
      // Display gallery
      const galleryContainer = document.getElementById('gallery');
      product.gallery.forEach(img => {
        const img_el = document.createElement('img');
        img_el.src = img.url;
        img_el.alt = product.name;
        galleryContainer.appendChild(img_el);
      });
      
      // Display specifications
      const specsContainer = document.getElementById('specifications');
      product.specifications.forEach(spec => {
        specsContainer.innerHTML += `
          <div class="spec-row">
            <span class="spec-key">${spec.key}:</span>
            <span class="spec-value">${spec.value}</span>
          </div>
        `;
      });
      
      // Display features
      const featuresContainer = document.getElementById('features');
      product.features.forEach(feature => {
        const li = document.createElement('li');
        li.textContent = feature;
        featuresContainer.appendChild(li);
      });
      
      // Display reviews
      const reviewsContainer = document.getElementById('reviews');
      data.reviews.forEach(review => {
        reviewsContainer.innerHTML += `
          <div class="review-card">
            <div class="review-header">
              <strong>${review.user}</strong>
              <span class="rating">⭐ ${review.rating}/5</span>
            </div>
            <p>${review.text}</p>
            <small>${new Date(review.created_at).toLocaleDateString()}</small>
          </div>
        `;
      });
      
      // Set SEO metadata
      document.title = product.seo.title;
      document.querySelector('meta[name="description"]').content = product.seo.description;
      document.querySelector('meta[name="keywords"]').content = product.seo.keywords;
      
      // Load related products
      loadRelatedProducts(productId);
    }
  }
  
  async function loadRelatedProducts(productId) {
    const response = await fetch(`/store/api/products/related/${productId}?limit=4`);
    const data = await response.json();
    
    const container = document.getElementById('related-products');
    data.products.forEach(product => {
      container.innerHTML += `
        <a href="/store/product/${product.slug}" class="related-product">
          <img src="${product.image_url}" alt="${product.name}">
          <h4>${product.name}</h4>
          <div>⭐ ${product.rating}</div>
          <div>₹${product.price}</div>
        </a>
      `;
    });
  }
  
  document.addEventListener('DOMContentLoaded', loadProductDetail);
</script>

<input type="hidden" id="product-id" value="{{ product.id }}">
<div id="gallery" class="gallery"></div>
<div id="product-name" class="product-name"></div>
<div id="product-rating" class="product-rating"></div>
<div id="product-price" class="product-price"></div>
<div id="specifications" class="specifications"></div>
<div id="features" class="features"></div>
<div id="reviews" class="reviews"></div>
<div id="related-products" class="related-products"></div>
```

---

## 🛒 Checkout Integration

### Apply Coupon Code
```javascript
async function applyCoupon(couponCode) {
  // Validate coupon on checkout page
  const response = await fetch('/store/api/coupons/validate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      code: couponCode,
      cart_total: cartTotal,
      products: cartProducts
    })
  });
  
  const data = await response.json();
  if (data.success) {
    document.getElementById('discount-amount').textContent = `₹${data.discount}`;
    document.getElementById('final-total').textContent = `₹${data.final_total}`;
  } else {
    showError(data.error);
  }
}
```

---

## 📊 Admin Operations

### Add Product via CMS
```bash
# POST to /admin/store/product/create
{
  "name": "New Product",
  "slug": "new-product",
  "sku": "AUTO-GENERATED",
  "category": "Electronics",
  "subcategory": "Laptops",
  "brand": "TechBrand",
  "price_inr": 50000,
  "discount_price_inr": 45000,
  "stock": 100,
  "low_stock_threshold": 10,
  "gst_percent": 18,
  "status": "published",
  "is_featured": true,
  "description": "Product description...",
  "spec_key[]": ["Color", "Size"],
  "spec_value[]": ["Black", "Large"],
  "feature[]": ["Feature 1", "Feature 2"],
  "tags": "tag1, tag2",
  "warranty": "1 Year",
  "video_url": "https://youtube.com/...",
  "seo_title": "SEO Title",
  "seo_description": "SEO Description",
  "seo_keywords": "keyword1, keyword2",
  "image": [MULTIPART FILE],
  "gallery_images[]": [MULTIPART FILES]
}
```

### Manage Featured Products on Homepage
```bash
# POST to /admin/store/homepage/featured/add
{
  "section_id": 1,
  "product_id": 123,
  "highlight_text": "BESTSELLER",
  "highlight_color": "#f43f5e"
}
```

### Create Promotional Banner
```bash
# POST to /admin/store/homepage/banner/create
{
  "name": "Summer Sale Banner",
  "banner_image": [MULTIPART FILE],
  "alt_text": "Summer Sale",
  "target_url": "/store?sale=summer",
  "placement": "hero",
  "start_date": "2024-06-01",
  "end_date": "2024-06-30",
  "is_active": true
}
```

---

## 🔍 SEO Best Practices

### Meta Tags Implementation
```html
<!-- In product detail page header -->
<meta name="title" content="{{ product.seo_title }}">
<meta name="description" content="{{ product.seo_description }}">
<meta name="keywords" content="{{ product.seo_keywords }}">
<link rel="canonical" href="{{ product.seo_canonical_url }}">

<!-- Open Graph for social sharing -->
<meta property="og:title" content="{{ product.seo_title }}">
<meta property="og:description" content="{{ product.seo_description }}">
<meta property="og:image" content="{{ product.seo_og_image or product.image_url }}">
<meta property="og:url" content="{{ request.url }}">
<meta property="og:type" content="product">

<!-- Schema markup for rich snippets -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "{{ product.name }}",
  "description": "{{ product.description }}",
  "image": "{{ product.image_url }}",
  "brand": {
    "@type": "Brand",
    "name": "{{ product.brand }}"
  },
  "offers": {
    "@type": "Offer",
    "priceCurrency": "INR",
    "price": "{{ product.discount_price or product.price }}",
    "availability": "{% if product.in_stock %}InStock{% else %}OutOfStock{% endif %}",
    "url": "{{ request.url }}"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "{{ product.rating }}",
    "ratingCount": "{{ product.reviews_count }}"
  }
}
</script>
```

---

## 🚀 Performance Tips

### Lazy Loading Images
```html
<img src="placeholder.jpg" 
     data-src="/uploads/products/..." 
     alt="Product"
     loading="lazy">
```

### Pagination for Large Catalogs
```javascript
// Always use pagination
const page = new URLSearchParams(window.location.search).get('page') || 1;
const response = await fetch(`/store/api/products/search?page=${page}&per_page=12`);
```

### Cache API Responses
```javascript
// Cache categories (changes rarely)
localStorage.setItem('categories', JSON.stringify(categoriesData));
const cachedCategories = JSON.parse(localStorage.getItem('categories'));
```

---

## ⚠️ Error Handling

```javascript
async function safeApiCall(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!data.success) throw new Error(data.error);
    return data;
  } catch (error) {
    console.error('API Error:', error);
    showUserMessage('Failed to load data. Please refresh the page.');
    return null;
  }
}
```

---

## 📝 Checklist for Frontend Implementation

- [ ] Add product search to store homepage
- [ ] Implement category filtering
- [ ] Create product detail page
- [ ] Display product gallery with lightbox
- [ ] Show customer reviews section
- [ ] Implement featured products carousel
- [ ] Add SEO meta tags to all pages
- [ ] Setup related products section
- [ ] Implement coupon validation at checkout
- [ ] Add low stock warning
- [ ] Optimize images (lazy loading)
- [ ] Test all API endpoints
- [ ] Setup error handling
- [ ] Verify mobile responsiveness

---

**Last Updated:** May 22, 2026
**API Version:** 1.0
**Status:** Ready for Production
