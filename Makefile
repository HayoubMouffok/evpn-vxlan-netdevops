netbox:
	docker compose -f netbox/docker-compose.yml up -d
seed:
	python scripts/seed_netbox.py
render:
	python scripts/render.py
deploy: render
	sudo containerlab deploy -t build/fabric.clab.yml --reconfigure
test:
	sudo python -m pytest -v tests
destroy:
	sudo containerlab destroy -t build/fabric.clab.yml --cleanup
.PHONY: netbox seed render deploy test destroy
