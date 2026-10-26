export type GalleryImage = {
  url: string;
  local: string;
};

export type Sku = {
  id: string;
  listed_name: string;
  specification: string;
  dosage_form: string;
  indications: string;
  manufacturer: string;
  marketing_authorization_holder: string;
  production_address: string;
  detail_url: string;
  cover: string;
  cover_local: string | null;
  images: string[];
};

export type Product = {
  id: string;
  name: string;
  aliases: string[];
  category: string;
  summary: string;
  indications: string;
  indication_variants: string[];
  dosage_forms: string[];
  manufacturers: string[];
  authorization_holders: string[];
  sku_count: number;
  image_count: number;
  featured: boolean;
  cover: string;
  cover_local: string;
  gallery: GalleryImage[];
  skus: Sku[];
};

export type Catalog = {
  source: string;
  site_name: string;
  section: string;
  category: string;
  sku_count: number;
  product_count: number;
  featured: string[];
  products: Product[];
};
