import scrapy
from scrapy_playwright.page import PageMethod
from parsel import Selector
from amazonscraper.items import AmazonscraperItem


class AmazonSpiderSpider(scrapy.Spider):
    name = "amazon_spider"

    custom_settings = {
        "HTTP_PROXY": "https://scrapeops:734d1db2-da46-49e2-b96e-08db43fdd445@residential-proxy.scrapeops.io:8181?country=ng"
    }

    def start_requests(self):
        url = "https://www.amazon.com"

        actions = [
            PageMethod('wait_for_selector', '#twotabsearchtextbox'),
            PageMethod("locator", "input#twotabsearchtextbox"),
            PageMethod("click", "input#twotabsearchtextbox", force=True),
            PageMethod('type', '#twotabsearchtextbox', 'laptops', delay=150),
            PageMethod("click", "#nav-search-submit-button", force=True),
            PageMethod('wait_for_load_state', 'networkidle'),
        ]

        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_page_methods": actions,
                "playwright_include_page": True,
                "errback": self.errback,
            },
            callback=self.parse_results
        )

    async def parse_results(self, response):
        page = response.meta["playwright_page"]
        html = await page.content()
        await page.close()

        sel = Selector(text=html)

        # Extract all product URLs
        product_links = sel.css('a.a-link-normal.s-no-outline::attr(href)').getall()

        for href in product_links:
            full_url = response.urljoin(href)
            yield scrapy.Request(full_url, callback=self.parse_product)

        # Find NEXT PAGE link
        next_page = sel.css("a.s-pagination-next::attr(href)").get()

        if next_page:
            next_url = response.urljoin(next_page)

            # next pages DO NOT need Playwright again unless Amazon blocks HTML requests
            # but to be safe we use Playwright for all Amazon pages
            yield scrapy.Request(
                next_url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod('wait_for_selector', 'span.s-pagination-item'),
                        PageMethod('wait_for_load_state', 'networkidle'),
                    ],
                    "playwright_include_page": True,
                    "errback": self.errback,
                },
                callback=self.parse_results
            )

    def parse_product(self, response):
        # Extract product details from product page
        amazon_item = AmazonscraperItem()
        amazon_item['description'] = response.css("#productTitle::text").get(),
        amazon_item['price'] = response.css("span.a-price-whole::text").get(),
        amazon_item['url'] = response.url
        yield amazon_item


    async def errback(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
