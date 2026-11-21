from django.core.management.base import BaseCommand
from marketplace.models import Category
class Command(BaseCommand):
    help = 'Create the default ChoreMarket service categories'
    def handle(self, *args, **options):
        rows = [
            ('Laundry','laundry','Laundry pickup, washing and folding','♧'),
            ('Groceries','groceries','Market runs and grocery shopping','▤'),
            ('Cleaning','cleaning','Home and room cleaning','✧'),
            ('Repairs','repairs','Small home repairs and maintenance','⌁'),
            ('Tutoring','tutoring','Learning support and tutoring','▣'),
            ('Delivery','delivery','Local pickup and delivery','➜'),
        ]
        for name, slug, description, icon in rows:
            Category.objects.update_or_create(slug=slug, defaults={'name':name,'description':description,'icon':icon})
        self.stdout.write(self.style.SUCCESS('Default categories are ready.'))
