source "https://rubygems.org"

# This is the default theme for new Jekyll sites
gem "jekyll-theme-minimal"

# If you want to use GitHub Pages, uncomment the line below
# To upgrade, run `bundle update github-pages`
gem "github-pages", group: :jekyll_plugins
gem "jekyll", "~> 3.9.0"

# GitHub Pages dependencies
group :jekyll_plugins do
  gem "jekyll-feed", "~> 0.15"
  gem "jekyll-seo-tag", "~> 2.8"
end

# Windows does not include zoneinfo files, so bundle the tzinfo-data gem
# and associated library
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

# Performance-booster for watching directories on Windows
gem "wdm", "~> 0.1.1", platforms: [:mingw, :x64_mingw, :mswin]

# Lock `http_parser.rb` to `v0.6.x` on JRuby builds, because newer versions of
# this gem do not have a Java counterpart.
gem "http_parser.rb", "~> 0.6.0", platforms: [:jruby]
